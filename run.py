import requests
import json
import re
from lxml import etree
import csv
import time
import random
import demjson3
from params import *

# --- 配置区域 ---
MAX_RETRIES = 5
MIN_DELAY = 3.0
MAX_DELAY = 6.0
TIMEOUT = 15
CSV_FILE = 'data.csv'

# 随机 User-Agent
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]

type_dict = {'1': '留言', '2': '回复', '3': '点赞'}

def get_random_headers():
    new_headers = headers.copy() if 'headers' in globals() else {}
    new_headers.update({
        'User-Agent': random.choice(USER_AGENTS),
        'Referer': 'https://user.qzone.qq.com/',
        'Origin': 'https://user.qzone.qq.com',
    })
    return new_headers

def parse_qzone_json(text):
    """解析 dirty json"""
    match = re.search(r'_Callback\(([\s\S]*?)\);?$', text.strip())
    if match:
        text = match.group(1)
    else:
        text = text.strip().strip('()')
    
    text = text.replace('undefined', 'null')
    
    try:
        return demjson3.decode(text)
    except demjson3.JSONDecodeError:
        # 如果解析失败，尝试暴力正则提取 data 部分（作为最后的手段）
        return None

def fetch_data_with_retry(offset):
    url = 'https://user.qzone.qq.com/proxy/domain/ic2.qzone.qq.com/cgi-bin/feeds/feeds2_html_pav_all'
    current_params = params.copy()
    current_params['offset'] = str(offset)
    
    for attempt in range(MAX_RETRIES):
        try:
            sleep_time = random.uniform(MIN_DELAY, MAX_DELAY)
            if attempt > 0: sleep_time *= 2
            time.sleep(sleep_time)
            
            resp = requests.get(url, params=current_params, cookies=cookies, headers=get_random_headers(), timeout=TIMEOUT)
            
            if resp.status_code == 200:
                if 'login' in resp.text and 'location' in resp.text:
                    print("❌ Cookie 已失效（检测到登录跳转）")
                    return None
                return resp.text
            elif resp.status_code == 403:
                print("⚠️ 403 Forbidden，暂停 10 秒")
                time.sleep(10)
        except Exception as e:
            print(f"⚠️ 网络请求异常: {e}")
    return None

# --- 主程序 ---

if __name__ == '__main__':
    # 初始化 CSV
    with open(CSV_FILE, 'w', encoding='utf-8-sig', newline='') as wf:
        writer = csv.writer(wf)
        writer.writerow(['行为', '发起人昵称', '发起人qq号', '时间', '发起人空间', '有效内容', 'html页面'])

    page = 0
    empty_count = 0 
    
    # 【新增】用于记录已经爬过的动态，防止死循环
    seen_keys = set()

    print("🚀 开始抓取...")

    while True:
        print(f'\n📄 正在抓取第 {page//10 + 1} 页 (Offset: {page})')
        
        raw_text = fetch_data_with_retry(page)
        if not raw_text: break
            
        try:
            js = parse_qzone_json(raw_text)
            if not js:
                print("❌ JSON 解析失败，跳过此页")
                page += 10
                continue
            
            items = js.get('data')
            
            # 智能层级探测
            if items is None:
                # ... (保持原来的空检查逻辑) ...
                empty_count += 1
                if empty_count >= 3: break
                page += 10; continue
            elif isinstance(items, dict):
                if 'data' in items and isinstance(items['data'], list): items = items['data']
                elif 'feeds' in items and isinstance(items['feeds'], list): items = items['feeds']
                else: items = []
            elif isinstance(items, str): items = []

            if not items or len(items) == 0:
                if empty_count >= 3:
                    print("🛑 连续多次无数据，结束抓取。")
                    break
                print("⚠️ 当前页无数据，尝试下一页")
                empty_count += 1
                page += 10
                continue
                
            empty_count = 0 
            
            # 【新增】本页新数据计数器
            new_items_on_this_page = 0
            
            rows_to_write = []
            for i, item in enumerate(items):
                try:
                    if not isinstance(item, dict): continue

                    # 获取关键字段
                    act_qq = item.get('uin', '')
                    dt = item.get('feedstime', '')
                    act_name = item.get('nickname', '未知')
                    
                    # 【关键步骤】生成唯一指纹 (QQ号 + 发布时间)
                    # 也可以加上 item.get('key') 如果存在的话，但 QQ号+时间 通常足够唯一
                    unique_key = f"{act_qq}_{dt}"
                    
                    # 检查是否重复
                    if unique_key in seen_keys:
                        # 这是一个重复的动态，跳过写入，也不增加新数据计数
                        continue
                    
                    # 记录这个新动态
                    seen_keys.add(unique_key)
                    new_items_on_this_page += 1

                    # ... (原本的数据提取和解析逻辑) ...
                    act_type = str(item.get('typeid', ''))
                    act_home = item.get('userHome', '')
                    html = item.get('html', '').strip()
                    extract_text = ''
                    comments_list = ''
                    
                    if html:
                        html_xpath = etree.HTML(html)
                        if html_xpath is not None:
                            txt_list = html_xpath.xpath('//div[contains(@class,"txt-box")]//text()')
                            extract_text = ' '.join([t.strip() for t in txt_list if t.strip()])
                            if type_dict.get(act_type) == '回复':
                                cmt_list = html_xpath.xpath('//div[@class="mod-comments"]//text()')
                                comments_list = '\n'.join([c.strip() for c in cmt_list if c.strip()])

                    act_type_name = type_dict.get(act_type, '其它')
                    final_content = extract_text + (f"\n[评论]\n{comments_list}" if comments_list else "")
                    
                    rows_to_write.append([act_type_name, act_name, act_qq, dt, '', final_content, html])
                    print(f"   └─ {act_name}: {extract_text[:15]}...")

                except Exception as e:
                    print(f"   ⚠️ 单条错误: {e}")
                    continue

            # 【新增】判断本页是否全是重复数据
            if new_items_on_this_page == 0:
                print("\n🛑 触发去重机制：当前页所有数据都已存在。")
                print("这意味着服务器在重复返回最后一页，或者已经没有新内容了。")
                print("🎉 任务完成，正常退出。")
                break
            else:
                print(f"✅ 本页写入 {new_items_on_this_page} 条新数据 (过滤掉 {len(items) - new_items_on_this_page} 条重复)")

            with open(CSV_FILE, 'a', encoding='utf-8-sig', newline='') as wf:
                writer = csv.writer(wf)
                writer.writerows(rows_to_write)
            
            # 翻页
            page += 10
            
            # 随机延迟
            sleep_time = random.uniform(2, 4)
            print(f"   ⏳ 休息 {sleep_time:.1f} 秒...")
            time.sleep(sleep_time)
            
        except Exception as e:
            print(f"❌ 未知错误: {e}")
            break

    print(f"🎉 结束。共抓取 {len(seen_keys)} 条不重复动态。")
