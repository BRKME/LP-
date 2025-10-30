#!/usr/bin/env python3
"""
Uniswap V3 Analyzer with Telegram notifications
Automated script for finding high APR pools on Arbitrum and BSC
"""

import asyncio
import aiohttp
import pandas as pd
from datetime import datetime
import os
import sys
from telegram import Bot
from telegram.error import TelegramError

class UniswapAnalyzer:
    def __init__(self):
        # Minimum TVL threshold
        self.MIN_TVL = 1000000  # $1,000,000
        self.MIN_APR = 15  # Минимальный APR 15%
        
        # Telegram настройки
        self.telegram_token = "8442392037:AAEiM_b4QfdFLqbmmc1PXNvA99yxmFVLEp8"
        self.chat_id = "350766421"
        self.telegram_enabled = True
        
        # Target tokens
        self.target_tokens = [
            'USDT', 'USDC', 'USDC.e', 'WETH', 'ETH', 'sETH', 'WBTC', 
            'LINK', 'CRV', 'AAVE', 'SOL', 'ASTER', 'BNB', 'DAI', 
            'ARB', 'PENDLE', 'ZRO'
        ]
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        print(f"🤖 Telegram configured: {self.telegram_enabled}")
    
    async def send_telegram_message(self, message: str):
        """Send message to Telegram"""
        if not self.telegram_enabled:
            return False
            
        try:
            bot = Bot(token=self.telegram_token)
            await bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            print("✅ Telegram message sent successfully")
            return True
        except Exception as e:
            print(f"❌ Failed to send Telegram message: {e}")
            return False
    
    async def send_telegram_results(self, network_pools: dict):
        """Send analysis results to Telegram"""
        if not self.telegram_enabled:
            return
            
        arbitrum_pools = network_pools['arbitrum']
        bsc_pools = network_pools['bsc']
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        message = f"🚀 <b>Uniswap V3 Weekly Analysis</b>\n"
        message += f"⏰ <i>{timestamp} (MSK)</i>\n"
        message += f"📊 Min TVL: ${self.MIN_TVL:,} | Min APR: {self.MIN_APR}%\n\n"
        
        # Arbitrum pools
        if arbitrum_pools:
            message += "🔹 <b>ARBITRUM NETWORK</b>\n"
            for i, pool in enumerate(arbitrum_pools[:5], 1):
                message += (f"{i}. {pool['Pool']}\n"
                          f"   📈 APR: <b>{pool['Est. APR (%)']}%</b>\n"
                          f"   💰 TVL: ${pool['TVL (USD)']:,}\n"
                          f"   🔍 Source: {pool['Source']}\n\n")
        else:
            message += "🔹 <b>ARBITRUM NETWORK</b>\nNo pools found\n\n"
        
        # BSC pools
        if bsc_pools:
            message += "🔸 <b>BSC NETWORK</b>\n"
            for i, pool in enumerate(bsc_pools[:5], 1):
                message += (f"{i}. {pool['Pool']}\n"
                          f"   📈 APR: <b>{pool['Est. APR (%)']}%</b>\n"
                          f"   💰 TVL: ${pool['TVL (USD)']:,}\n"
                          f"   🔍 Source: {pool['Source']}\n\n")
        else:
            message += "🔸 <b>BSC NETWORK</b>\nNo pools found\n\n"
        
        # Summary
        total_pools = len(arbitrum_pools) + len(bsc_pools)
        message += f"📈 <b>Total pools found: {total_pools}</b>\n\n"
        message += "⚡ <i>Automated weekly report</i>"
        
        await self.send_telegram_message(message)
    
    async def fetch_defillama_yields(self):
        """Fetch yield data from DeFiLlama"""
        url = "https://yields.llama.fi/pools"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    data = await response.json()
                    pools = data.get('data', [])
                    
                    filtered_pools = [
                        p for p in pools 
                        if p.get('tvlUsd', 0) >= self.MIN_TVL 
                        and p.get('apy', 0) >= self.MIN_APR
                        and p.get('chain') in ['Arbitrum', 'BSC']
                        and 'uniswap' in p.get('project', '').lower()
                    ]
                    
                    return filtered_pools
        except Exception as e:
            print(f"❌ DeFiLlama API error: {e}")
            return []
    
    async def fetch_uniswap_graph_arbitrum(self):
        """Fetch pools from Uniswap Graph API for Arbitrum"""
        query = """
        {
          pools(
            first: 200
            where: {
              totalValueLockedUSD_gt: %d
            }
            orderBy: totalValueLockedUSD
            orderDirection: desc
          ) {
            id
            token0 { symbol id }
            token1 { symbol id }
            totalValueLockedUSD
            feesUSD
            poolDayData(first: 7, orderBy: date, orderDirection: desc) {
              feesUSD
              date
            }
          }
        }
        """ % self.MIN_TVL
        
        url = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json={'query': query}, headers=self.headers) as response:
                    data = await response.json()
                    return data.get('data', {}).get('pools', [])
        except Exception as e:
            print(f"❌ Uniswap Arbitrum Graph API error: {e}")
            return []
    
    async def fetch_uniswap_graph_bsc(self):
        """Fetch pools from Uniswap Graph API for BSC"""
        query = """
        {
          pools(
            first: 200
            where: {
              totalValueLockedUSD_gt: %d
            }
            orderBy: totalValueLockedUSD
            orderDirection: desc
          ) {
            id
            token0 { symbol id }
            token1 { symbol id }
            totalValueLockedUSD
            feesUSD
            poolDayData(first: 7, orderBy: date, orderDirection: desc) {
              feesUSD
              date
            }
          }
        }
        """ % self.MIN_TVL
        
        url = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3-bsc"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json={'query': query}, headers=self.headers) as response:
                    data = await response.json()
                    return data.get('data', {}).get('pools', [])
        except Exception as e:
            print(f"❌ Uniswap BSC Graph API error: {e}")
            return []
    
    def calculate_v3_apr(self, pool_data, days=7):
        """Calculate APR for V3 pools from fee data"""
        try:
            if not pool_data.get('poolDayData'):
                return 0
            
            available_days = min(days, len(pool_data['poolDayData']))
            if available_days == 0:
                return 0
            
            total_fees = sum(float(day_data.get('feesUSD', 0)) for day_data in pool_data['poolDayData'][:available_days])
            daily_fees = total_fees / available_days
            tvl = float(pool_data.get('totalValueLockedUSD', 1))
            
            if tvl == 0:
                return 0
            
            daily_apr = daily_fees / tvl
            annual_apr = daily_apr * 365
            return annual_apr * 100
            
        except Exception as e:
            return 0
    
    async def analyze_arbitrum_pools(self):
        """Analyze Arbitrum pools"""
        defillama_pools, graph_pools = await asyncio.gather(
            self.fetch_defillama_yields(),
            self.fetch_uniswap_graph_arbitrum(),
            return_exceptions=True
        )
        
        defillama_pools = defillama_pools if not isinstance(defillama_pools, Exception) else []
        graph_pools = graph_pools if not isinstance(graph_pools, Exception) else []
        
        all_pools = []
        
        # Process DeFiLlama pools
        arbitrum_defillama = [p for p in defillama_pools if p.get('chain') == 'Arbitrum']
        for pool in arbitrum_defillama:
            all_pools.append({
                'Pool': pool.get('symbol', 'Unknown'),
                'Network': 'ARBITRUM',
                'Est. APR (%)': round(pool.get('apy', 0)),
                'TVL (USD)': round(pool.get('tvlUsd', 0)),
                'Source': 'DeFiLlama'
            })
        
        # Process Graph API pools
        for pool in graph_pools:
            token0 = pool['token0']['symbol']
            token1 = pool['token1']['symbol']
            pool_name = f"{token0}-{token1}"
            tvl = float(pool.get('totalValueLockedUSD', 0))
            
            if tvl >= self.MIN_TVL:
                apr = self.calculate_v3_apr(pool, 7)
                if apr >= self.MIN_APR:
                    all_pools.append({
                        'Pool': pool_name,
                        'Network': 'ARBITRUM',
                        'Est. APR (%)': round(apr),
                        'TVL (USD)': round(tvl),
                        'Source': 'Uniswap Graph'
                    })
        
        return all_pools[:10]  # Return top 10
    
    async def analyze_bsc_pools(self):
        """Analyze BSC pools"""
        defillama_pools, graph_pools = await asyncio.gather(
            self.fetch_defillama_yields(),
            self.fetch_uniswap_graph_bsc(),
            return_exceptions=True
        )
        
        defillama_pools = defillama_pools if not isinstance(defillama_pools, Exception) else []
        graph_pools = graph_pools if not isinstance(graph_pools, Exception) else []
        
        all_pools = []
        
        # Process DeFiLlama pools
        bsc_defillama = [p for p in defillama_pools if p.get('chain') == 'BSC']
        for pool in bsc_defillama:
            all_pools.append({
                'Pool': pool.get('symbol', 'Unknown'),
                'Network': 'BSC',
                'Est. APR (%)': round(pool.get('apy', 0)),
                'TVL (USD)': round(pool.get('tvlUsd', 0)),
                'Source': 'DeFiLlama'
            })
        
        # Process Graph API pools
        for pool in graph_pools:
            token0 = pool['token0']['symbol']
            token1 = pool['token1']['symbol']
            pool_name = f"{token0}-{token1}"
            tvl = float(pool.get('totalValueLockedUSD', 0))
            
            if tvl >= self.MIN_TVL:
                apr = self.calculate_v3_apr(pool, 7)
                if apr >= self.MIN_APR:
                    all_pools.append({
                        'Pool': pool_name,
                        'Network': 'BSC',
                        'Est. APR (%)': round(apr),
                        'TVL (USD)': round(tvl),
                        'Source': 'Uniswap Graph'
                    })
        
        return all_pools[:10]  # Return top 10
    
    async def analyze_all_networks(self):
        """Analyze pools across all networks"""
        print("🔄 Analyzing pools from multiple sources...")
        
        if self.telegram_enabled:
            await self.send_telegram_message("🔄 <b>Starting weekly Uniswap V3 analysis...</b>")
        
        arbitrum_pools, bsc_pools = await asyncio.gather(
            self.analyze_arbitrum_pools(),
            self.analyze_bsc_pools(),
            return_exceptions=True
        )
        
        arbitrum_pools = arbitrum_pools if not isinstance(arbitrum_pools, Exception) else []
        bsc_pools = bsc_pools if not isinstance(bsc_pools, Exception) else []
        
        return {
            'arbitrum': arbitrum_pools,
            'bsc': bsc_pools
        }

async def main():
    """Main execution function"""
    analyzer = UniswapAnalyzer()
    
    try:
        print("🔧 Uniswap V3 Weekly Analyzer")
        print("=" * 50)
        
        network_pools = await analyzer.analyze_all_networks()
        
        # Display results in console
        arbitrum_pools = network_pools['arbitrum']
        bsc_pools = network_pools['bsc']
        
        if arbitrum_pools:
            print(f"\n🔹 ARBITRUM NETWORK (Top {len(arbitrum_pools)}):")
            for pool in arbitrum_pools:
                print(f"   {pool['Pool']} - APR: {pool['Est. APR (%)']}% - TVL: ${pool['TVL (USD)']:,}")
        
        if bsc_pools:
            print(f"\n🔸 BSC NETWORK (Top {len(bsc_pools)}):")
            for pool in bsc_pools:
                print(f"   {pool['Pool']} - APR: {pool['Est. APR (%)']}% - TVL: ${pool['TVL (USD)']:,}")
        
        # Send to Telegram
        if analyzer.telegram_enabled:
            await analyzer.send_telegram_results(network_pools)
            print(f"\n✅ Results sent to Telegram! Total pools: {len(arbitrum_pools) + len(bsc_pools)}")
        
    except Exception as e:
        error_msg = f"❌ Analysis failed: {e}"
        print(error_msg)
        if analyzer.telegram_enabled:
            await analyzer.send_telegram_message(f"❌ <b>Analysis Failed</b>\n{error_msg}")

if __name__ == "__main__":
    asyncio.run(main())
