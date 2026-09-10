"""Structured application failures shared by services and CLI adapters."""


class CommandError(Exception):
    def __init__(self, message, code='invalid_input', exit_code=2):
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code
