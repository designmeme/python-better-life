import datetime
import logging
import os
import time
import traceback
import pprint
import sys

import asyncio
import dotenv
import pandas as pd
import requests

import telegrambot

logger = logging.getLogger(__name__)
dotenv.load_dotenv()


def main(goods_code: str, sleep_sec: int = 60):
    session = requests.Session()
    session.headers.update({
        "Host": "api-ticketfront.interpark.com",
        "Accept-Encoding": "gzip",
        # "Accept-Encoding": "gzip,deflate,br",
        "Accept": "*/*",
        "Connection": "keep-alive",
        "Referer": "https://fiddle.jshell.net/",
        "Cache-Control": "no-cache",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    })

    url = f"https://tickets.interpark.com/goods/{goods_code}"
    api_summary_url = f"https://api-ticketfront.interpark.com/v1/goods/{goods_code}/summary?goodsCode={goods_code}"
    res = session.get(api_summary_url)
    summary = res.json()["data"]
    # pprint.pp(summary)

    name = summary["goodsName"]
    KST = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(tz=datetime.timezone.utc).astimezone(KST)
    booking_open_date = summary["ticketOpenDate"]  # format ex) 202510181100
    booking_open_date = datetime.datetime.strptime(booking_open_date, "%Y%m%d%H%M").replace(tzinfo=KST)
    booking_end_date = summary["bookingEndDate"]  # format ex) 202510181100
    booking_end_date = datetime.datetime.strptime(booking_end_date, "%Y%m%d%H%M").replace(tzinfo=KST)

    if now < booking_open_date or now > booking_end_date:
        logger.debug(f"인터파크 티켓 빈 좌석 알림: 예약 시간 아님. {booking_open_date=} {booking_end_date=}")
        return

    api_play_seq_url = (f"https://api-ticketfront.interpark.com/v1/goods/{goods_code}/playSeq?"
                        f"startDate={summary['playStartDate']}&endDate={summary['playEndDate']}"
                        f"&goodsCode={goods_code}&isBookableDate=true&page=1&pageSize=1550")
    res = session.get(api_play_seq_url)
    play_seq = res.json()["data"]
    # pprint.pp(play_seq)

    def check_seats():
        all_remain_seats = []
        for seq in play_seq:
            play_date = seq["playDate"] + '' + seq["playTime"]
            api_seat_url = f"https://api-ticketfront.interpark.com/v1/goods/{goods_code}/playSeq/PlaySeq/{seq['playSeq']}/REMAINSEAT"
            res = session.get(api_seat_url)
            data = res.json()["data"]
            # pprint.pp(data)
            remain_seats = list(filter(lambda x: x["remainCnt"] > 0, data["remainSeat"]))

            if remain_seats:
                all_remain_seats.append({
                    'play_date': play_date,
                    'remain_seats': remain_seats,
                })

        if all_remain_seats:
            text = ['인터파크 티켓 빈 좌석 알림', name]
            for x in all_remain_seats:
                seats = [f"{y['seatGradeName']} {y['remainCnt']}" for y in x['remain_seats']]
                seats = ', '.join(seats)
                text.append(f"{x['play_date']} {seats}")

            text.append(url)
            text = "\n".join(text)
            asyncio.run(telegrambot.send_message(text))

    # 주기적으로 요청하기
    while True:
        check_seats()
        now = datetime.datetime.now(tz=datetime.timezone.utc).astimezone(KST)
        if now < booking_open_date or now > booking_end_date:
            logger.debug(f"인터파크 티켓 빈 좌석 알림: 예약 시간 아님. {booking_open_date=} {booking_end_date=}")
            return
        time.sleep(sleep_sec)


if __name__ == "__main__":
    # print(sys.argv)
    logging.basicConfig(level=logging.DEBUG)
    goods_code = sys.argv[1]
    sleep_sec = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    logger.debug(f"인터파크 티켓 빈 좌석 알림 start: {goods_code=!r}")
    main(goods_code, sleep_sec)
