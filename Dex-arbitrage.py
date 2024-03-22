# -*- coding: utf-8 -*-
"""
Created on Thu Mar  7 02:02:39 2024

@author: yarno
"""

import os
import sys
from eulith_web3.signing import LocalSigner, construct_signing_middleware
from eulith_web3.eulith_web3 import *
from eulith_web3.erc20 import TokenSymbol
from eulith_web3.swap import *
from eulith_web3.exceptions import EulithRpcException
import logging

sys.path.insert(0, os.getcwd())
from config import PRIVATE_KEY, EULITH_TOKEN
from eulith_web3.utils.banner import print_banner

logging.basicConfig(filename='file.log', format='%(asctime)s-%(levelname)s-%(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)

wallet = LocalSigner(PRIVATE_KEY)
ew3_arbitrum = EulithWeb3("https://arb-main.eulithrpc.com/v0", EULITH_TOKEN, construct_signing_middleware(wallet))
ew3_ethereum = EulithWeb3("https://eth-main.eulithrpc.com/v0", EULITH_TOKEN, construct_signing_middleware(wallet))

dexs = [EulithLiquiditySource.UNISWAP_V3, EulithLiquiditySource.BALANCER_V2, EulithLiquiditySource.SUSHI,
        EulithLiquiditySource.COMPOUND, EulithLiquiditySource.PANCAKE, EulithLiquiditySource.CURVE_V2,
        EulithLiquiditySource.CURVE_V1, EulithLiquiditySource.SADDLE, EulithLiquiditySource.SYNAPSE,
        EulithLiquiditySource.BALANCER_V1]

weth = ew3.eulith_get_erc_token(TokenSymbol.WETH)
usdt = ew3.eulith_get_erc_token(TokenSymbol.USDT)
usdc = ew3.eulith_get_erc_token(TokenSymbol.USDC)
link = ew3.eulith_get_erc_token(TokenSymbol.LINK)
matic = ew3.eulith_get_erc_token(TokenSymbol.MATIC)
bnb = ew3.eulith_get_erc_token(TokenSymbol.BNB)
busd = ew3.eulith_get_erc_token(TokenSymbol.BUSD)
steth = ew3.eulith_get_erc_token(TokenSymbol.STETH)
ldo = ew3.eulith_get_erc_token(TokenSymbol.LDO)
crv = ew3.eulith_get_erc_token(TokenSymbol.CRV)
cvx = ew3.eulith_get_erc_token(TokenSymbol.CVX)
badger = ew3.eulith_get_erc_token(TokenSymbol.BADGER)
bal = ew3.eulith_get_erc_token(TokenSymbol.BAL)
oneinch = ew3.eulith_get_erc_token(TokenSymbol.ONEINCH)
uni = ew3.eulith_get_erc_token(TokenSymbol.UNI)
ape = ew3.eulith_get_erc_token(TokenSymbol.APE)
gmt = ew3.eulith_get_erc_token(TokenSymbol.GMT)

transaction_gas_usage = {
    "atomic_swap": 250000,
    "deposit": 28000,
    "token_transfer": 21000,
    "contract_deposit": 40000,
    "contract_withdrawal": 35000,
    "toolkit_funding": 115000,
    "contract_deployment": 500000
}

transaction_gas_limits = {transaction_type: gas_usage * 2 for transaction_type, gas_usage in 
                          transaction_gas_usage.items()}

def create_list_of_token_pair_tuples(tokens):
    
    if tokens == None:
        tokens = [weth, link, ldo, crv, uni, usdt, usdc]
    pairs = []
    for i in range(len(tokens)):
        for j in range(i+1, len(tokens)):
            pairs.append((tokens[i], tokens[j]))
            pairs.append((tokens[j], tokens[i]))
    return pairs

def fund_toolkit_contract_if_needed(sell_amount, sell_token):
    #sell_token's type is EulithERC20
  
    #create toolkit contract if doesn't exist already
    ew3.eulith_create_contract_if_not_exist(wallet.address)
    
    #fund proxy contract if insufficient sell token
    proxy_contract_address = ew3.eulith_contract_address(wallet.address)
    sell_token_proxy_balance = sell_token.balance_of_float(proxy_contract_address)
    
    if sell_token.address != "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48" and sell_token.address != "0xdAC17F958D2ee523a2206206994597C13D831ec7":
        sell_token_decimals = 1e18
    
    else:
        sell_token_decimals = 1e6
    
    sell_token_proxy_balance = sell_token_proxy_balance / sell_token_decimals
    
    if sell_token_proxy_balance < sell_amount:
        print('Funding toolkit contract')
        amount_to_send_in_sell_token = sell_amount - sell_token_proxy_balance
        tx = sell_token.transfer_float(proxy_contract_address, float(amount_to_send_in_sell_token * sell_token_decimals),
                                       override_tx_parameters={'from': wallet.address})
        rec = ew3.eth.send_transaction(tx)
        receipt = ew3.eth.wait_for_transaction_receipt(rec)
        print(f"Funding proxy contract, hash: {receipt['transactionHash'].hex()}")
        logging.info(f'Funding toolkit contract, sell token: {sell_token.symbol}, amount: {amount_to_send_in_sell_token}', exc_info=True)
        
    else:
        print("Proxy balance does not need funding")
        
def compute_sell_amount(sell_token):
    
    sell_amount_in_usdc = 10.0
    if sell_token.address != "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48" and sell_token.address != "0xdAC17F958D2ee523a2206206994597C13D831ec7":
        swap_params = EulithSwapRequest(sell_token=usdc, buy_token=sell_token, sell_amount=sell_amount_in_usdc)
            
        try:
            price_of_sell_token_in_usdc, txs = ew3.eulith_swap_quote(swap_params)
            
        except EulithRpcException:
            print(f"Failed to get swap quote for {sell_token.symbol}/usdc")
            logging.error(f'Failed to compute sell amount for {sell_token.symbol}, program ending..', exc_info=True)
            sys.exit (1)
            
            sell_amount = round(sell_amount_in_usdc / price_of_sell_token_in_usdc, 17)
            
    else:
        sell_amount = sell_amount_in_usdc
    
    return sell_amount
            
def get_min_dex_and_max_spread(sell_token, buy_token, sell_amount, slippage_tolerance):
    
    txs_per_dex = {}
    prices_per_dex = {}
    for dex in dexs:
        swap_params = EulithSwapRequest(
            sell_token=sell_token,
            buy_token=buy_token,
            sell_amount=sell_amount,
            liquidity_source=dex,
            recipient=ew3.eulith_contract_address(wallet.address),
            slippage_tolerance=slippage_tolerance)
        
        try:
            price, txs = ew3.eulith_swap_quote(swap_params)
            prices_per_dex[dex] = price
            txs_per_dex[dex] = txs
        
        except EulithRpcException:
            print(f"Failed to get quote from {dex.name}")
            continue
    
    if prices_per_dex and txs_per_dex:
        max_price_dex = max(prices_per_dex, key=prices_per_dex.get)
        min_price_dex = min(prices_per_dex, key=prices_per_dex.get)
        max_price = prices_per_dex[max_price_dex]
        min_price = prices_per_dex[min_price_dex]
        min_price_dex_txs = txs_per_dex[min_price_dex]
        spread = (max_price - min_price) / min_price
        
        return {
            'max_dex': (max_price_dex, max_price),
            'min_dex': (min_price_dex, min_price),
            'min_price_dex_txs': min_price_dex_txs,   #transactions needed to execute the trade, given the set of params
            'spread': spread
        }

def get_max_dex(sell_token, buy_token, sell_amount, slippage_tolerance):
    
    txs_per_dex = {}
    for dex in dexs:
        swap_params = EulithSwapRequest(
            sell_token=buy_token,
            buy_token=sell_token,
            sell_amount=sell_amount,
            liquidity_source=dex,
            recipient=wallet.address,
            slippage_tolerance=slippage_tolerance)
        
        try:
            price, txs = ew3.eulith_swap_quote(swap_params)
            txs_per_dex[dex] = txs
        
        except EulithRpcException:
            print(f"Failed to get txs from {dex.name}")
            continue
    
    if txs_per_dex:
        return txs_per_dex
    
def get_gas_cost_in_sell_token(transaction_type: str, sell_token):
    #sell token's type is EulithERC20
    
    if transaction_type not in transaction_gas_usage:
        print("Invalid transaction type")
        logging.error('Invalid transaction gas usage type', exc_info=True)
        sys.exit(1)
    
    max_gas_usage = transaction_gas_usage[transaction_type]
    price_per_gas_in_wei = ew3.eth.gas_price 
    price_per_gas_in_gwei = price_per_gas_in_wei / 1e9
    pending_block_base_fee = (ew3.eth.get_block('pending').baseFeePerGas) / 1e9
    priority_fee = abs(price_per_gas_in_gwei - pending_block_base_fee)
    price_per_gas_in_eth = price_per_gas_in_wei / 1e18
    max_gas_cost_in_eth = price_per_gas_in_eth * max_gas_usage
    
    if sell_token.address != "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2":
        #need to get a price for eth in the sell token, to calculate gas cost in the sell token
        swap_params = EulithSwapRequest(
            sell_token=sell_token,
            buy_token=weth,
            sell_amount=1.0)
        
        try:
            price_of_eth_in_sell_token, txs = ew3.eulith_swap_quote(swap_params)
        
        except EulithRpcException:
            print(f"Failed to get swap quote for weth/{sell_token.symbol}")
            logging.error('Failed to get swap quote for weth/{sell_token.symbol}, unable to compute gas price', exc_info=True )
            sys.exit(1)
        
        price_per_gas_in_sell_token = price_per_gas_in_eth * price_of_eth_in_sell_token
        max_gas_cost_in_sell_token = price_per_gas_in_sell_token * max_gas_usage
        
    else:   #if sell token is weth
        max_gas_cost_in_sell_token = max_gas_cost_in_eth
    
    return max_gas_cost_in_sell_token, price_per_gas_in_gwei, priority_fee, max_gas_usage

def print_trade_summary(initial_sell_amount, sell_token, post_arb_amount_in_sell_token, 
                        profitability, max_gas_cost_in_sell_token):
    print('\n~~~~~~~~~~~~~~~~~~Trade Summary~~~~~~~~~~~~~~~~~~~')
    print(f'Started with {initial_sell_amount} of {sell_token.symbol}')
    print(f'Ending with {post_arb_amount_in_sell_token} of {sell_token.symbol}')
    print(f'Profit: {profitability}%')
    print(f'Gas cost in {sell_token.symbol}: {max_gas_cost_in_sell_token}')
   
if __name__ == '__main__':
    
    logging.info('Application started', exc_info=True)
    print_banner()
    web_3_instances = [ew3_arbitrum, ew3_ethereum]
    asset_pairs = create_list_of_token_pair_tuples(None)
    slippage_tolerance = 0.3
    transaction_type = 'atomic_swap'
    
    try:
        
        while True:
            
            for asset_pair in asset_pairs:
                for ew3 in web_3_instances:
                    sell_token = asset_pair[1]
                    buy_token = asset_pair[0]
                    sell_amount = compute_sell_amount(sell_token)
                    initial_sell_amount = compute_sell_amount(sell_token)
                    print(f"Sell token is {sell_token.symbol}, Buy token is {buy_token.symbol}")
        
                    buy_leg_results = get_min_dex_and_max_spread(sell_token, buy_token, sell_amount, slippage_tolerance)               
                    if buy_leg_results == None:
                        print(f"Failed to retrieve results for {buy_token.symbol}/{sell_token.symbol}")
                        logging.error(f'Failed to retrieve results for {buy_token.symbol}/{sell_token.symbol}', exc_info=True)
                        sys.exit(1)
                    max_price_dex, max_price = buy_leg_results['max_dex']
                    min_price_dex, min_price = buy_leg_results['min_dex']
                    min_price_dex_txs = buy_leg_results['min_price_dex_txs']
                
                    sell_amount = round(sell_amount / min_price, 17)  #calculate imput to second leg, denominated in buy token  
                    sell_leg_results = get_max_dex(sell_token, buy_token, sell_amount, slippage_tolerance)
                    if sell_leg_results == None:
                        print(f"Failed to retrieve results for {sell_token.symbol}/{buy_token.symbol}")
                        logging.error(f'Failed to retrieve results for {sell_token.symbol}/{buy_token.symbol}', exc_info=True)
                        sys.exit(1)
                    max_price_dex_txs = sell_leg_results[max_price_dex]
        
                    post_arb_amount_in_sell_token = sell_amount * max_price
                    profit = post_arb_amount_in_sell_token - initial_sell_amount
        
                    max_gas_cost_in_sell_token, price_per_gas_in_gwei, priority_fee, max_gas_usage = get_gas_cost_in_sell_token(transaction_type, sell_token)
        
                    #check profitability
                    profitability = ((max_price - (min_price + max_gas_cost_in_sell_token)) / min_price) * 100
                    if (profitability - slippage_tolerance) > 0.6:
                    
                        fund_toolkit_contract_if_needed(initial_sell_amount, sell_token)
                    
                        ew3.eulith_start_transaction(wallet.address)
                        ew3.eulith_send_multi_transaction(min_price_dex_txs)
                        ew3.eulith_send_multi_transaction(max_price_dex_txs)
            
                        print_trade_summary(initial_sell_amount, sell_token, post_arb_amount_in_sell_token, 
                                        profitability, max_gas_cost_in_sell_token)
                        logging.info(
                            f'Arbitrage found. Started with {initial_sell_amount} of {sell_token.symbol}\n'
                            f'Ending with {post_arb_amount_in_sell_token} of {sell_token.symbol}\n'
                            f'Profit: {profitability}%\n'
                            f'Gas cost in {sell_token.symbol}: {max_gas_cost_in_sell_token}',
                            exc_info=True
                        )
                        
                        atomic_tx = ew3.eulith_commit_transaction()
            
                        #setting the gas limits
                        atomic_tx['maxFeePerGas'] = int(price_per_gas_in_gwei)
                        atomic_tx['maxPriorityFeePerGas'] = priority_fee
                        atomic_tx['gas'] = max_gas_usage
            
                        #send the transaction!
                        tx = ew3.eth.send_transaction(atomic_tx)
                        receipt = ew3.eth.wait_for_transaction_receipt(tx)
                        print(f" Transaction Executed \nWith receipt: {receipt['transactionHash'].hex()}")
                        logging.info(f"Transaction Executed \nWith receipt: {receipt['transactionHash'].hex()}", exc_info=True)
            
                    else:
                        print(f"Transaction not executed; profit would've been {profit}, max gas cost is {max_gas_cost_in_sell_token}")
                        print(f"The sell_token right now is: {sell_token.symbol}")
                        print(f"The buy_token right now is: {buy_token.symbol}")
                    
    except KeyboardInterrupt:
        logging.info('Program has been manually stopped', exc_info=True)
        print("Program has been manually stopped.")