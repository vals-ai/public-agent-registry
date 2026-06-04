from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from model_library.base.base import QueryResultCost, QueryResultMetadata
from model_library.base.input import SystemInput, ToolCall

from minisweagent.exceptions import FormatError
from minisweagent.models.vals_model import ValsModel

MOCK_IN_TOKENS = 100
MOCK_OUT_TOKENS = 50
MOCK_COST_INPUT = 0.008
MOCK_COST_OUTPUT = 0.002
MOCK_DURATION_SECONDS = 1.5


def _mock_tool_call(name="bash", args=None, call_id="call_a"):
    return ToolCall(id=call_id, name=name, args=args or {"command": "echo hello"})


def _mock_metadata(with_cost=True, in_tokens=MOCK_IN_TOKENS, out_tokens=MOCK_OUT_TOKENS):
    cost = QueryResultCost(input=MOCK_COST_INPUT, output=MOCK_COST_OUTPUT) if with_cost else None
    return QueryResultMetadata(
        cost=cost,
        duration_seconds=MOCK_DURATION_SECONDS,
        in_tokens=in_tokens,
        out_tokens=out_tokens,
    )


def _mock_query_result(
    tool_calls=None, output_text="some text", with_cost=True, in_tokens=MOCK_IN_TOKENS, out_tokens=MOCK_OUT_TOKENS
):
    result = MagicMock()
    result.tool_calls = tool_calls or []
    result.output_text = output_text
    result.history = [MagicMock()]
    result.metadata = _mock_metadata(with_cost=with_cost, in_tokens=in_tokens, out_tokens=out_tokens)
    result.model_dump.return_value = {}
    return result


@patch("minisweagent.models.vals_model.get_registry_model")
class TestValsModelQuery:
    def _make_model(self, mock_get_model):
        mock_get_model.return_value = MagicMock()
        return ValsModel(model_name="anthropic/claude-haiku-4-5-20251001")

    def test_valid_tool_call_returns_actions(self, mock_get_model):
        model = self._make_model(mock_get_model)
        tc = _mock_tool_call(args={"command": "ls -la"}, call_id="call_a")
        model._model.query = AsyncMock(return_value=_mock_query_result(tool_calls=[tc]))

        result = model.query([{"role": "user", "content": "list files"}])
        assert result["extra"]["actions"] == [{"command": "ls -la", "tool_call_id": "call_a"}]
        assert result["role"] == "assistant"

    def test_no_tool_calls_raises_format_error(self, mock_get_model):
        model = self._make_model(mock_get_model)
        model._model.query = AsyncMock(return_value=_mock_query_result(tool_calls=[]))

        with pytest.raises(FormatError):
            model.query([{"role": "user", "content": "test"}])

    def test_unknown_tool_raises_format_error(self, mock_get_model):
        model = self._make_model(mock_get_model)
        tc = _mock_tool_call(name="unknown_tool", call_id="call_a")
        model._model.query = AsyncMock(return_value=_mock_query_result(tool_calls=[tc]))

        with pytest.raises(FormatError) as exc_info:
            model.query([{"role": "user", "content": "test"}])
        assert "Unknown tool" in exc_info.value.messages[0]["content"]

    def test_tool_calls_shape(self, mock_get_model):
        model = self._make_model(mock_get_model)
        tc = _mock_tool_call(args={"command": "pwd"}, call_id="call_a")
        model._model.query = AsyncMock(return_value=_mock_query_result(tool_calls=[tc]))

        result = model.query([{"role": "user", "content": "test"}])
        assert result["tool_calls"] == [
            {"id": "call_a", "function": {"name": "bash", "arguments": '{"command": "pwd"}'}, "type": "function"}
        ]

    def test_system_prompt_extracted_from_messages(self, mock_get_model):
        model = self._make_model(mock_get_model)
        tc = _mock_tool_call()
        model._model.query = AsyncMock(return_value=_mock_query_result(tool_calls=[tc]))

        model.query(
            [
                {"role": "system", "content": "test system prompt"},
                {"role": "user", "content": "test"},
            ]
        )
        call_kwargs = model._model.query.call_args.kwargs
        input_items = call_kwargs["input"]
        assert isinstance(input_items[0], SystemInput)
        assert input_items[0].text == "test system prompt"

    def test_no_system_message_passes_no_system_input(self, mock_get_model):
        model = self._make_model(mock_get_model)
        tc = _mock_tool_call()
        model._model.query = AsyncMock(return_value=_mock_query_result(tool_calls=[tc]))

        model.query([{"role": "user", "content": "test"}])
        call_kwargs = model._model.query.call_args.kwargs
        input_items = call_kwargs["input"]
        assert not any(isinstance(item, SystemInput) for item in input_items)

    def test_metrics_included_in_extra(self, mock_get_model):
        model = self._make_model(mock_get_model)
        tc = _mock_tool_call()
        mock_result = _mock_query_result(tool_calls=[tc])
        model._model.query = AsyncMock(return_value=mock_result)

        result = model.query([{"role": "user", "content": "test"}])
        metrics = result["extra"]["metrics"]
        expected_metadata = mock_result.metadata
        assert metrics["in_tokens"] == expected_metadata.in_tokens
        assert metrics["out_tokens"] == expected_metadata.out_tokens
        assert metrics["cost"]["total"] == expected_metadata.cost.total

    def test_metrics_without_cost(self, mock_get_model):
        model = self._make_model(mock_get_model)
        tc = _mock_tool_call()
        model._model.query = AsyncMock(return_value=_mock_query_result(tool_calls=[tc], with_cost=False))

        result = model.query([{"role": "user", "content": "test"}])
        assert result["extra"]["metrics"]["cost"] is None
        assert result["extra"]["cost"] == 0.0


@patch("minisweagent.models.vals_model.get_registry_model")
class TestValsModelMultiTurn:
    def _make_model(self, mock_get_model):
        mock_get_model.return_value = MagicMock()
        return ValsModel(model_name="test-model")

    def test_multi_turn_history_and_incremental_input(self, mock_get_model):
        model = self._make_model(mock_get_model)
        messages = [{"role": "user", "content": "first"}]

        turns = [
            {"cmd": "ls", "call_id": "call_a", "tool_output": "file_list"},
            {"cmd": "pwd", "call_id": "call_b", "tool_output": "/home/user"},
            {"cmd": "cat README", "call_id": "call_c", "tool_output": None},
        ]

        prev_history = []
        for i, turn in enumerate(turns):
            tc = _mock_tool_call(args={"command": turn["cmd"]}, call_id=turn["call_id"])
            mock_result = _mock_query_result(tool_calls=[tc])
            mock_result.history = [f"hist_{j}" for j in range(i + 1)]
            model._model.query = AsyncMock(return_value=mock_result)

            result = model.query(messages)

            call_kwargs = model._model.query.call_args.kwargs
            assert call_kwargs["history"] == prev_history
            assert result["extra"]["actions"] == [{"command": turn["cmd"], "tool_call_id": turn["call_id"]}]
            assert turn["call_id"] in model._last_tool_calls

            if i > 0:
                assert len(call_kwargs["input"]) == 1
                assert call_kwargs["input"][0].result == turns[i - 1]["tool_output"]

            prev_history = mock_result.history
            if turn["tool_output"]:
                messages.extend(
                    [
                        {"role": "assistant", "content": f"resp{i}"},
                        {"role": "tool", "content": turn["tool_output"], "tool_call_id": turn["call_id"]},
                    ]
                )

    def test_format_error_preserves_history_state(self, mock_get_model):
        """No tool calls will raise a FormatError, but history and index should
        still advance so the retry doesn't resend the same messages."""
        model = self._make_model(mock_get_model)
        result_without_tool_calls = _mock_query_result(tool_calls=[])
        result_without_tool_calls.history = ["updated_history"]
        model._model.query = AsyncMock(return_value=result_without_tool_calls)

        messages = [{"role": "user", "content": "test"}]
        with pytest.raises(FormatError):
            model.query(messages)

        assert model._history == ["updated_history"]
        assert model._msg_cursor == 1


@patch("minisweagent.models.vals_model.get_registry_model")
class TestValsModelFormatObservation:
    def test_formats_tool_result(self, mock_get_model):
        mock_get_model.return_value = MagicMock()
        model = ValsModel(model_name="test", observation_template="{{ output.output }}")
        message = {"extra": {"actions": [{"command": "echo test", "tool_call_id": "call_a"}]}}
        outputs = [{"output": "test output", "returncode": 0}]

        result = model.format_observation_messages(message, outputs)
        assert len(result) == 1
        assert result[0]["role"] == "tool"
        assert result[0]["tool_call_id"] == "call_a"
        assert result[0]["content"] == "test output"

    def test_no_actions_returns_empty(self, mock_get_model):
        mock_get_model.return_value = MagicMock()
        model = ValsModel(model_name="test")
        result = model.format_observation_messages({"extra": {}}, [])
        assert result == []
