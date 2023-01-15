import json
import logging
import os
import sys
import time
from http import HTTPStatus

import requests
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
        raise Exception(f'{error}, ошибка доступа к API практикума')


def get_api_answer(timestamp):
    """
    Функция обращается к эндпоинту API практикума.
    получает ответ и преобразует его.
    """
    payload = {'from_date': timestamp}
    try:
        answer = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except requests.RequestException as error:
        logger.error(f'Запросик к API не проходит, {error}')
        raise Exception(f'Запросик к API не проходит, {error}')
    try:
        content = answer.json()
    except json.decoder.JSONDecodeError as error:
        logger.error(f'Невозможно преобразовать ответ в JSON, {error}')
        raise Exception(f'Невозможно преобразовать ответ в JSON, {error}')
    if answer.status_code == HTTPStatus.OK:
        return content
    raise exceptions.ExceptionGetApiAnswerStatus(
        'Ошибка при запросе к API практикума'
    )


def check_response(response):
    """Функция проверяет наличие ключей в ответе API."""
    try:
        curr_date = response['current_date']
    except KeyError as error:
        logger.error(
            f'Ключ current_date не передается в ответе API, {error}'
        )
        raise Exception(
            f'Ключ current_date не передается в ответе API, {error}'
        )
    try:
        homeworks = response['homeworks']
    except KeyError as error:
        logger.error(
            f'Ключ homeworks не передается в ответе API, {error}'
        )
        raise Exception(f'Ключ homeworks не передается в ответе API, {error}')
    if isinstance(curr_date, int) and isinstance(homeworks, list):
        return homeworks
    raise TypeError('Неверный тип переданных данных')


def parse_status(homework):
    """Функция извлекает статус домашней работы из ответа API."""
    homework_name = homework.get('homework_name')
    if homework_name is None:
        raise exceptions.ExceptionKeyNotFound(
            'Ключа homework_name нет в ответе'
        )
    homework_status = homework.get('status')
    if homework_status is None:
        raise exceptions.ExceptionKeyNotFound(
            'Ключа homework_status нет в ответе'
        )
    if isinstance(homework, dict):
        if homework_status in HOMEWORK_VERDICTS:
            verdict = HOMEWORK_VERDICTS.get(homework_status)
            return(
                f'Изменился статус проверки работы "{homework_name}".; '
                f'{verdict}'
            )
        raise exceptions.ExceptionUnknownHomeworkStatus(
            'Неизвестный статус ДЗ'
        )
    raise TypeError('Неверный тип данных')


def main():
    """Основная логика работы бота."""
    try:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
    except Exception as error:
        logger.error(f'ошибка программы {error}')
    timestamp = int(time.time())
    temporary_status = []
    if not check_tokens():
        logger.critical('Отсутствуют переменные окружения')
        sys.exit('Отсутствуют переменные окружения')
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if not homework:
                logger.info('Пока пусто')
                time.sleep(RETRY_PERIOD)
                continue
            message = parse_status(homework[-1])
            if temporary_status != message:
                send_message(bot, message)
                temporary_status = message
            logger.info(f'Сообщение отправлено: {message}')
            timestamp = int(time.time())
            time.sleep(RETRY_PERIOD)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logger.info(f'сообщение отправлено: {message}')
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
