""" Script that monitors NFT transactions from whale wallets """
import os
import requests
import yaml

import pandas as pd
import requests

OPENSEA_WYVERN_V1 = '0x7be8076f4ea4a4ad08075c2508e481d6c946d12b'
OPENSEA_WYVERN_V2 = '0x7f268357a8c2552623316e2562d90e642bb538e5'
TOKEN = os.environ['ETHERSCAN_TOKEN']
DISCORD_BOT_TOKEN = os.environ['DISCORD_BOT_TOKEN']
CHANNEL_ID = int(os.environ['CHANNEL_ID'])
DISCORD_HEADER = {
    'Authorization': f'Bot {DISCORD_BOT_TOKEN}'
}


def get_721_txns(address, startblock=None):
    recs = requests.get(
        'https://api.etherscan.io/api',
        params=dict(
            module='account',
            action='tokennfttx',
            address=address,
            startblock=0 if startblock is None else startblock,
            apikey=TOKEN
        )
    ).json()['result']
    return recs


def get_opensea_value(txhash):
    internal = requests.get(
        'https://api.etherscan.io/api',
        params=dict(
            module='account',
            action='txlistinternal',
            txhash=txhash,
            apikey=TOKEN
        )
    ).json()['result']
    if internal:
        df = pd.DataFrame.from_records(internal)
        addrs = df['to'].tolist() + df['from'].tolist()
        is_opensea = (OPENSEA_WYVERN_V1 in addrs) or (OPENSEA_WYVERN_V2 in addrs)
        if is_opensea:
            return df.value.apply(int).sum() / 1e18
    return 0


def main():
    with open('config.yaml') as f:
        config = yaml.load(f, Loader=yaml.CLoader)
    wallet_list = [w.lower() for w in config['wallets'].values()]
    records = []
    for nickname, addr in config['wallets'].items():
        recs = get_721_txns(addr, startblock=config.get('last_block'))
        for r in recs:
            r['nickname'] =  nickname
        records += recs
    if len(records) == 0:
        return
    df = pd.DataFrame.from_records(records)
    df = df[(df['to'].isin(wallet_list)) | (df['from'].isin(wallet_list))]
    for _, row in df.iterrows():
        txhash, nickname, nft_name, nft_addr, nft_token_id = row[
            ['hash', 'nickname', 'tokenName', 'contractAddress', 'tokenID']
        ]
        val = get_opensea_value(txhash)
        if val > 0:
            action = 'bought' if row['to'] in wallet_list else 'sold'
            send_discord_msg(
                f'{nickname} just [{action}](https://etherscan.io/tx/{txhash}) a [{nft_name}]'
                f'(https://opensea.io/assets/{nft_addr}/{nft_token_id}) NFT worth {val:,.2f} ETH.',
                channel_id=CHANNEL_ID
            )
    config['last_block'] = df.blockNumber.apply(int).max()
    with open('config.yaml', 'w') as f:
        yaml.dump(config, f, Dumper=yaml.CDumper)
        

def send_discord_msg(msg, channel_id):
    requests.post(
        f'https://discord.com/api/channels/{channel_id}/messages',
        json={
            'embeds':[
                {
                    'title': 'Whale spotted  🐳',
                    'description': msg,
                }
            ]
        },
        headers=DISCORD_HEADER
    )


if __name__ == '__main__':
    main()
