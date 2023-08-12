import datetime
import logging
import os
import traceback

import asyncio
import dotenv
import requests

import telegrambot

logger = logging.getLogger(__name__)
dotenv.load_dotenv()


def notify_new_book_by_keyword(keyword: str):
    """신간 알림
    키워드로 검색한 결과에 신간 도서가 있다면 텔레그램 메세지로 알려준다.

    신간 기준: 검색 실행일 기준 하루 전에 발행한 경우

    네이버 책 검색 API 사용
    https://developers.naver.com/docs/serviceapi/search/book/book.md

    :param keyword: 검색어
    :return:
    """
    try:
        url = "https://openapi.naver.com/v1/search/book.json"
        headers = {
            "X-Naver-Client-Id": os.environ.get("NEVER_API_ID"),
            "X-Naver-Client-Secret": os.environ.get("NEVER_API_SECRET"),
        }
        params = {
            "query": keyword,
            "sort": "date",
        }
        logger.debug(f"신간 검색 요청. {keyword=!r}")
        res = requests.get(url, headers=headers, params=params)
        res.raise_for_status()

        books = res.json()["items"]
        logger.debug(f"검색 결과: {len(books)}개")

        new_books = []
        today = datetime.date.today()
        for book in books:
            pubdate = datetime.date.fromisoformat(book["pubdate"])
            diff = today - pubdate
            if diff.days == 1:  # 어제 출간된 도서만
                new_books.append(book)

        # 신간 도서가 있다면 메세지를 발송한다.
        logger.debug(f"신간 검색 결과: {len(new_books)}개")

        if new_books:
            text = [f"*신간 알림* - 검색어 \"{keyword}\""]
            text += [f"- [{b['title']}]({b['link']}) | 발행일 {b['pubdate']}" for b in new_books]
            text = "\n".join(text)
            asyncio.run(telegrambot.send_message(text, "Markdown"))
    except Exception as e:
        logger.error(traceback.format_exception())
        text = f"신간 알림 코드 실행 중 오류가 발생했어요. {e}"
        asyncio.run(telegrambot.send_message(text, "Markdown"))


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    keywords = os.environ.get("NEW_BOOK_KEYWORDS")
    logger.debug(f"신간 알림 키워드: {keywords!r}")
    keywords = keywords.split(",")
    for k in keywords:
        notify_new_book_by_keyword(k)
