# Uniswap V3 Weekly Analyzer 🤖

Automated weekly analysis of Uniswap V3 pools on Arbitrum and BSC networks. The script finds high APR liquidity pools and sends results to Telegram.

## Features

- 🔍 **Multi-source analysis**: DeFiLlama + Uniswap Graph API
- 🌐 **Multi-network**: Arbitrum + BSC
- 💰 **Smart filtering**: Min TVL $1M + Min APR 15%
- 📱 **Telegram notifications**: Formatted results
- ⏰ **Automated**: Runs weekly on Saturdays at 10:00 AM Moscow time

## Telegram Output

The bot sends formatted messages with:
- Top 5 pools from each network
- APR percentages
- TVL amounts
- Data sources

## Setup

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
