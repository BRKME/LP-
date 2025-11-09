#!/usr/bin/env python3
"""
Uniswap V3 Analyzer with Telegram notifications
Simplified version for GitHub Actions
"""

import asyncio
import aiohttp
import json
from datetime import datetime
import locale

class UniswapAnalyzer:
    def __init__(self):
        # Minimum thresholds
        self.MIN_TVL = 600000  # $600,000
        self.MIN_APR = 10  # Minimum APR 10%
        
        # Telegram settings
        self.telegram_token = "8442392037:AAEiM_b4QfdFLqbmmc1PXNvA99yxmFVLEp8"
        self.chat_id = "350766421"
        
        # Target tokens - все токены (без ограничений)
        self.target_tokens = []
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }
    
    def get_formatted_date(self):
        """Get formatted date string in Russian format"""
        now = datetime.now()
        
        # Russian day names
        days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
        months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
                  'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
        
        day_name = days[now.weekday()]
        day = now.day
        month = months[now.month - 1]
        week_number = now.isocalendar()[1]
        
        return f"{day_name} {day} {month}, неделя {week_number}"
    
    async def send_telegram_message(self, message: str):
        """Send message to Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        print("✅ Telegram message sent successfully")
                        return True
                    else:
                        error_text = await response.text()
                        print(f"❌ Telegram API error: {error_text}")
                        return False
        except Exception as e:
            print(f"❌ Failed to send Telegram message: {e}")
            return False
    
    def is_target_pool(self, token0: str, token1: str) -> bool:
        """Check if pool contains target tokens (всегда True если нет ограничений)"""
        if not self.target_tokens:
            return True
        
        norm_token0 = self.normalize_token_symbol(token0)
        norm_token1 = self.normalize_token_symbol(token1)
        
        return (norm_token0 in self.target_tokens or norm_token1 in self.target_tokens)
    
    def normalize_token_symbol(self, symbol: str) -> str:
        """Normalize token symbol for consistent matching"""
        if not symbol:
            return symbol
            
        symbol_upper = symbol.upper().strip()
        
        # Token aliases
        token_aliases = {
            'ASTER': ['ASTER', 'ASTR'],
            'BNB': ['BNB', 'WBNB'],
            'DAI': ['DAI'],
            'PENDLE': ['PENDLE'],
            'ZRO': ['ZRO', 'ZROOM'],
            'ETH': ['ETH', 'WETH', 'SETH'],
            'USDC.e': ['USDC.E', 'USDC-E', 'USDC_E']
        }
        
        for main_token, aliases in token_aliases.items():
            if symbol_upper in aliases or symbol_upper == main_token:
                return main_token
        
        return symbol_upper
    
    async def fetch_defillama_yields(self):
        """Fetch yield data from DeFiLlama"""
        url = "https://yields.llama.fi/pools"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        pools = data.get('data', [])
                        
                        # Filter pools
                        filtered_pools = [
                            p for p in pools 
                            if p.get('tvlUsd', 0) >= self.MIN_TVL 
                            and p.get('apy', 0) >= self.MIN_APR
                            and p.get('chain') in ['Arbitrum', 'BSC']
                            and 'uniswap' in p.get('project', '').lower()
                        ]
                        return filtered_pools
                    else:
                        print(f"❌ DeFiLlama API returned status: {response.status}")
                        return []
        except asyncio.TimeoutError:
            print("❌ DeFiLlama API timeout")
            return []
        except Exception as e:
            print(f"❌ DeFiLlama API error: {e}")
            return []
    
    async def fetch_uniswap_graph(self, subgraph_url: str, network: str):
        """Fetch pools from Uniswap Graph API"""
        query = """
        {
          pools(
            first: 100
            where: {
              totalValueLockedUSD_gt: %d
            }
            orderBy: totalValueLockedUSD
            orderDirection: desc
          ) {
            id
            token0 { symbol }
            token1 { symbol }
            totalValueLockedUSD
            feesUSD
            poolDayData(first: 7, orderBy: date, orderDirection: desc) {
              feesUSD
              date
            }
          }
        }
        """ % self.MIN_TVL
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    subgraph_url, 
                    json={'query': query}, 
                    headers=self.headers,
                    timeout=30
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        pools = data.get('data', {}).get('pools', [])
                        
                        # Filter pools by target tokens
                        filtered_pools = [
                            p for p in pools 
                            if self.is_target_pool(
                                p['token0']['symbol'], 
                                p['token1']['symbol']
                            )
                        ]
                        
                        print(f"✅ Fetched {len(filtered_pools)} target pools from {network}")
                        return filtered_pools
                    else:
                        print(f"❌ {network} Graph API returned status: {response.status}")
                        return []
        except asyncio.TimeoutError:
            print(f"❌ {network} Graph API timeout")
            return []
        except Exception as e:
            print(f"❌ {network} Graph API error: {e}")
            return []
    
    def calculate_v3_apr(self, pool_data, days=7):
        """Calculate APR for V3 pools from fee data"""
        try:
            if not pool_data.get('poolDayData'):
                return 0
            
            available_days = min(days, len(pool_data['poolDayData']))
            if available_days == 0:
                return 0
            
            total_fees = sum(
                float(day_data.get('feesUSD', 0)) 
                for day_data in pool_data['poolDayData'][:available_days]
            )
            daily_fees = total_fees / available_days
            tvl = float(pool_data.get('totalValueLockedUSD', 1))
            
            if tvl == 0:
                return 0
            
            daily_apr = daily_fees / tvl
            annual_apr = daily_apr * 365
            return annual_apr * 100
            
        except Exception as e:
            return 0
    
    async def analyze_network(self, network: str, subgraph_url: str):
        """Analyze pools for a specific network"""
        print(f"🔍 Analyzing {network} pools...")
        
        # Fetch data from both sources
        defillama_pools, graph_pools = await asyncio.gather(
            self.fetch_defillama_yields(),
            self.fetch_uniswap_graph(subgraph_url, network),
            return_exceptions=True
        )
        
        # Handle exceptions
        defillama_pools = defillama_pools if not isinstance(defillama_pools, Exception) else []
        graph_pools = graph_pools if not isinstance(graph_pools, Exception) else []
        
        all_pools = []
        
        # Process DeFiLlama pools for this network
        network_defillama = [
            p for p in defillama_pools 
            if p.get('chain', '').lower() == network.lower()
        ]
        
        for pool in network_defillama:
            all_pools.append({
                'Pool': pool.get('symbol', 'Unknown'),
                'Network': network.upper(),
                'APR': round(pool.get('apy', 0)),
                'TVL': round(pool.get('tvlUsd', 0)),
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
                        'Network': network.upper(),
                        'APR': round(apr),
                        'TVL': round(tvl),
                        'Source': 'Uniswap Graph'
                    })
        
        # Remove duplicates and sort by APR
        unique_pools = {}
        for pool in all_pools:
            pool_key = pool['Pool']
            if pool_key not in unique_pools or pool['APR'] > unique_pools[pool_key]['APR']:
                unique_pools[pool_key] = pool
        
        sorted_pools = sorted(unique_pools.values(), key=lambda x: x['APR'], reverse=True)
        return sorted_pools[:8]  # Return top 8 pools
    
    async def send_results_to_telegram(self, arbitrum_pools, bsc_pools):
        """Send formatted results to Telegram"""
        formatted_date = self.get_formatted_date()
        
        message = f"#Крипта #Best LP\n"
        message += f"{formatted_date}\n\n"
        message += f"📊 Min TVL: ${self.MIN_TVL:,} | Min APR: {self.MIN_APR}%\n\n"
        
        # Arbitrum pools
        if arbitrum_pools:
            message += "🔹 <b>ARBITRUM NETWORK</b>\n"
            for i, pool in enumerate(arbitrum_pools[:5], 1):
                message += (f"{i}. {pool['Pool']}\n"
                          f"   📈 APR: <b>{pool['APR']}%</b>\n"
                          f"   💰 TVL: ${pool['TVL']:,}\n"
                          f"   🔍 {pool['Source']}\n\n")
        else:
            message += "🔹 <b>ARBITRUM NETWORK</b>\nNo pools found\n\n"
        
        # BSC pools
        if bsc_pools:
            message += "🔸 <b>BSC NETWORK</b>\n"
            for i, pool in enumerate(bsc_pools[:5], 1):
                message += (f"{i}. {pool['Pool']}\n"
                          f"   📈 APR: <b>{pool['APR']}%</b>\n"
                          f"   💰 TVL: ${pool['TVL']:,}\n"
                          f"   🔍 {pool['Source']}\n\n")
        else:
            message += "🔸 <b>BSC NETWORK</b>\nNo pools found\n\n"
        
        # Summary
        total_pools = len(arbitrum_pools) + len(bsc_pools)
        message += f"📈 <b>Total pools found: {total_pools}</b>\n\n"
        message += "⚡ <i>Automated weekly report</i>"
        
        await self.send_telegram_message(message)
    
    async def run_analysis(self):
        """Main analysis function"""
        print("🔧 Uniswap V3 Weekly Analyzer")
        print("=" * 50)
        print(f"📊 Min TVL: ${self.MIN_TVL:,} | Min APR: {self.MIN_APR}%")
        print("🎯 Target tokens: All tokens")
        print("=" * 50)
        
        # Define subgraph URLs
        subgraphs = {
            'arbitrum': 'https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3',
            'bsc': 'https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3-bsc'
        }
        
        # Analyze both networks in parallel
        arbitrum_pools, bsc_pools = await asyncio.gather(
            self.analyze_network('arbitrum', subgraphs['arbitrum']),
            self.analyze_network('bsc', subgraphs['bsc'])
        )
        
        # Display results in console
        print(f"\n📊 ANALYSIS RESULTS:")
        print(f"🔹 Arbitrum: {len(arbitrum_pools)} pools")
        for pool in arbitrum_pools[:3]:
            print(f"   {pool['Pool']} - {pool['APR']}% APR - ${pool['TVL']:,} TVL")
        
        print(f"🔸 BSC: {len(bsc_pools)} pools")
        for pool in bsc_pools[:3]:
            print(f"   {pool['Pool']} - {pool['APR']}% APR - ${pool['TVL']:,} TVL")
        
        # Send to Telegram
        print("\n📱 Sending results to Telegram...")
        await self.send_results_to_telegram(arbitrum_pools, bsc_pools)
        
        print(f"✅ Analysis completed! Total pools found: {len(arbitrum_pools) + len(bsc_pools)}")

async def main():
    """Main execution function"""
    try:
        analyzer = UniswapAnalyzer()
        await analyzer.run_analysis()
    except Exception as e:
        print(f"❌ Critical error: {e}")
        # Try to send error to Telegram
        try:
            analyzer = UniswapAnalyzer()
            await analyzer.send_telegram_message(f"❌ <b>Analysis Failed</b>\n{str(e)}")
        except:
            pass

if __name__ == "__main__":
    asyncio.run(main())
