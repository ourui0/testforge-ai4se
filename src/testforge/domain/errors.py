class TestForgeError(Exception):
    pass


class InputError(TestForgeError):
    pass


class ConfigurationError(TestForgeError):
    pass


class CredentialError(TestForgeError):
    pass


class LLMError(TestForgeError):
    pass


class SandboxError(TestForgeError):
    pass


class ToolExecutionError(TestForgeError):
    pass


class PolicyViolation(TestForgeError):
    pass


class StaleWorkspaceError(TestForgeError):
    pass


class InvalidTransition(TestForgeError):
    def __init__(self, state: object, event: object) -> None:
        state_value = getattr(state, "value", str(state))
        event_value = getattr(event, "value", str(event))
        super().__init__(f"event {event_value} is invalid from state {state_value}")
