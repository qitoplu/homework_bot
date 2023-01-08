import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import simplejson
import telegram
from dotenv import load_dotenv

import exceptions

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    filemode='a',
    format='%(asctime)s, %(levelname)s, %(message)s'
)
logger = logging.getLogger(__name__)
logger.addHandler(
    logging.StreamHandler()
)


def check_tokens():
    """Функция проверяет доступность переменных окружения."""
    tokens = {
        'practikum_token': PRACTICUM_TOKEN,
        'tg_token': TELEGRAM_TOKEN,
        'chat_id': TELEGRAM_CHAT_ID,
    }
    for key, value in tokens.items():
        if value is None:
            logger.critical(f'{key} отсутствует переменная окружения')
            return False
    return True


def send_message(bot, message):
    """Функция отправляет сообщение пользователю в телеграмм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение отправлено')
    except telegram.TelegramError as error:
        logger.error(f'{error}, ошибка доступа к API практикума')
        sys.exit


def get_api_answer(timestamp):
    """
    Функция обращается к эндпоинту API практикума.
    получает ответ и преобразует его.
    """
    payload = {'from_date': timestamp}
    try:
        answer = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except requests.RequestException:
        logger.error('Запросик к API не проходит')
        sys.exit
    try:
        content = answer.json()
    except simplejson.JSONDecodeError:
        logger.error('Невозможно преобразовать ответ в JSON')
        sys.exit
    if answer.status_code == HTTPStatus.OK:
        return content
    raise exceptions.ExceptionGetApiAnswerStatus(
        'Ошибка при запросе к API практикума'
    )


def check_response(response):
    """Функция проверяет наличие ключей в ответе API."""
    try:
        curr_date = response['current_date']
    except KeyError:
        logger.error(
            'Ключ current_date не передается в ответе API'
        )
        sys.exit
    try:
        homeworks = response['homeworks']
    except KeyError:
        logger.error(
            'Ключ homeworks не передается в ответе API'
        )
        sys.exit
    if isinstance(curr_date, int) and isinstance(homeworks, list):
        return homeworks
    raise TypeError('Неверный тип переданных данных')


def parse_status(homework):
    """Функция извлекает статус домашней работы из ответа API."""
    try:
        homework_name = homework['homework_name']
    except homework_name['homework_name'] == []:
        raise exceptions.ExceptionKeyNotFound(
            'Ключа homework_name нет в ответе'
        )
    try:
        homework_status = homework['status']
    except homework_status['status'] == []:
        raise exceptions.ExceptionKeyNotFound(
            'Ключа homework_status нет в ответе'
        )
    if homework_status in HOMEWORK_VERDICTS:
        verdict = str(HOMEWORK_VERDICTS[homework['status']])
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    raise exceptions.ExceptionUnknownHomeworkStatus(
        'Неизвестный статус ДЗ'
    )


def main():
    """Основная логика работы бота."""
    if check_tokens():
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            quantity = len(homework)
            message = parse_status(homework[quantity - 1])
            send_message(bot, message)
            logger.info(f'Сообщение отправлено: {message}')
            quantity -= 1
            timestamp = int(time.time())
            time.sleep(RETRY_PERIOD)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logger.info(f'сообщение отправлено: {message}')
            time.sleep(RETRY_PERIOD)
            sys.exit


if __name__ == '__main__':
    main()
