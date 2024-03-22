# Project Dex-Arbitrage
Multi level Dex-arbitrage strategy for iterating through multiple token pairs, for token pairs - multiple blockchains, 
and for blockchains - multiple dex's. Perform an arbitrage via atomic transaction if a trade is deemed profitable 
after considering for dynamic fees and slippage.
## Requirements
- Python >= 3.7
- Eulith API key
- Metamask private key
- To install required libraries: `pip install -r requirements.txt`, the main library here that enables the sdk is `eulith-web3`
- Fund your wallet with the base token for all pairs traded (can be adjusted), and with ETH to cover gas fees
## Keys
The Eulith API key, and the Metamask private key, are stored in a config file located in the same directory as the scripts. It 
has the following contents:
`EULITH_TOKEN = "insert_api_key_here"`
`PRIVATE_KEY = "insert_private_key_here"`
