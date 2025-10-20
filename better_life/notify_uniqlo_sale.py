import asyncio
import logging
import os
import re
import time

import dotenv
import pandas as pd
import requests
from requests.adapters import HTTPAdapter

import telegrambot

logger = logging.getLogger(__name__)
dotenv.load_dotenv()


def main(product_url: str):
    adapter = HTTPAdapter(max_retries=10)
    session = requests.Session()
    session.mount("https://", adapter)

    url = f"https://www.uniqlo.com/kr/ko/products/{product_url}"
    session.headers.update({
        "Host": "www.uniqlo.com",
        "Accept-Encoding": "gzip",
        # "Accept-Encoding": "gzip,deflate,br",
        "Accept": "*/*",
        "Connection": "keep-alive",
        "Referer": url,
        "Cache-Control": "no-cache",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    })

    product_id = product_url.split("/")[0]
    price_group = product_url.split("/")[1].split("?")[0]
    color_code = re.search(r"colorDisplayCode=(\d+)", product_url).group(1)
    size_code = re.search(r"sizeDisplayCode=(\d+)", product_url).group(1)

    detail_url = f"https://www.uniqlo.com/kr/api/commerce/v5/ko/products/{product_id}/price-groups/{price_group}/details?includeModelSize=false&imageRatio=3x4&httpFailure=true"
    res = session.get(detail_url)
    data = res.json()["result"]
    # pprint.pp(data)

    name = data['name']

    # 색상, 사이즈별 재고 및 가격 확인
    size_url = f"https://www.uniqlo.com/kr/api/commerce/v5/ko/products/{product_id}/price-groups/{price_group}/l2s?withPrices=true&withStocks=true&storeId=113326&includePreviousPrice=true&httpFailure=true"
    res = session.get(size_url)
    data = res.json()["result"]
    # pprint.pp(data)

    products = [x for x in data['l2s'] if x['color']['displayCode'] == color_code and x['size']['displayCode'] == size_code]
    if not len(products):
        print(f"no product found: {color_code} {size_code}")
        return
    product = products[0]
    productL2Id = product['l2Id']
    # pprint.pp(product)

    price_info = data['prices'][productL2Id]
    # pprint.pp(price_info)
    # {'base': {'currency': {'code': 'KRW', 'symbol': '₩'}, 'value': 29900},
    #  'promo': None,
    #  'isDualPrice': False,
    #  'taxPolicy': 'INCLUSIVE'}
    # {'base': {'currency': {'code': 'KRW', 'symbol': '₩'}, 'value': 29900},
    #  'promo': {'currency': {'code': 'KRW', 'symbol': '₩'}, 'value': 19900},
    #  'isDualPrice': True,
    #  'discountPercentage': None,
    #  'taxPolicy': 'INCLUSIVE'}
    base_price = price_info['base']['value']
    promo_price = price_info['promo']['value'] if price_info['promo'] else None

    stock_info = data['stocks'][productL2Id]
    # pprint.pp(stock_info)
    # {'statusCode': 'IN_STOCK',
    #  'quantity': 11,
    #  'transitStatus': 'NO_TRANSIT',
    #  'backInStock': False,
    #  'disableSizeChip': False,
    #  'storeStockStatus': 'IN_STOCK',
    #  'storePurchaseFlag': False,
    #  'transitLocalized': '',
    #  'statusLocalized': '재고 있음',
    #  'isDCStock': False}
    # {'statusCode': 'STOCK_OUT',
    #  'quantity': 0,
    #  'transitStatus': 'NO_TRANSIT',
    #  'backInStock': True,
    #  'disableSizeChip': True,
    #  'storeStockStatus': 'OUT_OF_STOCK',
    #  'storePurchaseFlag': False,
    #  'transitLocalized': '',
    #  'statusLocalized': '품절',
    #  'isDCStock': False}
    stock_status = stock_info['statusLocalized']

    directory = os.environ.get("CACHE_DIR")
    if not os.path.isdir(directory):
        os.makedirs(directory)
    cache_file = os.path.join(directory, 'uniqlo_sale.csv')
    cache_key = product_url

    try:
        cache_df = pd.read_csv(cache_file, index_col=0)
        cache_product = cache_df[cache_df['key'] == cache_key]
        cache_product = cache_product.iloc[0] if len(cache_product) else None
    except FileNotFoundError:
        cache_df = None
        cache_product = None
    # print(cache_df)

    is_promo = bool(promo_price)
    if is_promo and (cache_product is None or cache_product['promo'] != is_promo):
        flags = product['flags']['priceFlags']
        discount_flag = [x for x in flags if x['code'] == 'discount'][0]

        texts = [
            f"유니클로 상품 할인 알림",
            f"<b>{name}</b>",
            f"{discount_flag['name']}",
            f"{base_price:,} → {promo_price:,} ({stock_status})",
            f'<a href="{url}">상품 페이지</a>',
        ]
        text = "\n".join(texts)
        asyncio.run(telegrambot.send_message(text))

    if cache_df is None:
        cache_df = pd.DataFrame(columns=['key', 'name', 'promo'], data=[{'key': cache_key, 'name': name, 'promo': is_promo}])
    else:
        if cache_product is not None:
            cache_df.loc[cache_df['key'] == cache_key, 'promo'] = is_promo
        else:
            cache_df = pd.concat([cache_df, pd.DataFrame(columns=['key', 'name', 'promo'], data=[{'key': cache_key, 'name': name, 'promo': is_promo}])])
            cache_df = cache_df.reset_index(drop=True)
    # print('new', cache_df)
    cache_df.to_csv(cache_file)


if __name__ == "__main__":
    # print(sys.argv)
    logging.basicConfig(level=logging.DEBUG)

    items = os.environ.get("UNIQLO_PRODS")
    items = items.split(",")
    for i, item in enumerate(items):
        if i > 0:
            time.sleep(1)
        main(item)
