import datetime
import logging
import os
import traceback

import asyncio
import dotenv
import pandas as pd
import requests

import telegrambot

logger = logging.getLogger(__name__)
dotenv.load_dotenv()


_pattern = {i: '\\' + chr(i) for i in b'()[]{}?*+-|^$\\.&~#'}


def notify_new_book_by_keyword(keyword: str, file: str):
    """신간 알림
    키워드로 검색한 결과에 신간 도서가 있다면 텔레그램 메세지로 알려준다.
    메세지로 보낸 도서는 .cache/book.csv 파일에 저장되며 다음 알림에서 제외된다.

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
            "display": 20,
        }
        logger.debug(f"신간 검색 요청. {keyword=!r}")
        res = requests.get(url, headers=headers, params=params)
        res.raise_for_status()

        books = res.json()["items"]
        books = pd.DataFrame(books)
        books = books.set_index("isbn")
        books['pubdate'] = pd.to_datetime(books['pubdate'])
        logger.debug(f"검색 결과: {len(books)}개.\n{books[['pubdate', 'title']]}")

        today = datetime.datetime.fromisoformat(datetime.date.today().isoformat())

        # 어제 이후 출간된 도서만
        new_books = books[books['pubdate'] >= today - datetime.timedelta(days=1)]

        # 이미 발송한 도서
        directory = os.path.dirname(os.path.abspath(file))
        if not os.path.isdir(directory):
            os.makedirs(directory)
        try:
            old_books = pd.read_csv(file, index_col="isbn", dtype={"isbn": str},
                                    parse_dates=["pubdate"])
            # 이미 발송한 도서 제외
            new_books = new_books[~new_books.index.isin(old_books.index.tolist())]
        except FileNotFoundError:
            old_books = None

        # 신간 도서가 있다면 메세지를 발송한다.
        logger.debug(f"신간 검색 결과: {len(new_books)}개")

        if len(new_books) > 0:
            text = [f"*신간 알림* - 검색어 \"{keyword}\""]
            for i, (isbn, b) in enumerate(new_books.iterrows()):
                text.append(f"{i + 1}. {b['pubdate'].strftime('%Y-%m-%d')} [{b['title'].translate(_pattern)}]({b['link']})")

            # 메세지 발송 책을 캐시 파일로 저장한다. (description 내용이 길어서 삭제함)
            cache_books = pd.concat([new_books, old_books]) if old_books is not None else new_books
            cache_books.drop("description", axis=1).to_csv(file, date_format="%Y-%m-%d")
        else:
            pass
            # text = [f"*신간 알림* - 검색어 \"{keyword}\""]
            # text += [f"- 없음"]

        text = "\n".join(text)
        # logger.debug(text)
        asyncio.run(telegrambot.send_message(text, "Markdown"))

    except Exception as e:
        logger.error(traceback.format_exception())
        text = f"신간 알림 코드 실행 중 오류가 발생했어요. {e}"
        asyncio.run(telegrambot.send_message(text, "Markdown"))


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    keywords = os.environ.get("NEW_BOOK_KEYWORDS")
    file = os.environ.get("BOOK_CACHE_FILE")
    logger.debug(f"신간 알림 키워드: {keywords!r}")
    keywords = keywords.split(",")
    for k in keywords:
        notify_new_book_by_keyword(k, file)
