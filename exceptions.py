class ExceptionGetApiAnswerStatus(Exception):
    """Исключение для функции get_api_answer."""

    pass


class ExceptionKeyNotFound(Exception):
    """Исключение для функции parse_status."""

    pass


class ExceptionUnknownHomeworkStatus(Exception):
    """
    Исключение для функции parse_status в случае.
    получения неизвестного статуса ДЗ.
    """

    pass
