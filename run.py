import requests
import json
import re
from lxml import etree
import csv
from params import *


type_dict = {
    '1':'留言',
    '2':'回复',
    '3':'点赞',
}
jsonize_keys=['main', 'hasMoreFeeds', 'true', 'total_number', 'offset', 'count', 'begin_time', 'end_time', 'getappnotification', 'has_get', 'host_more', 'data', 'ver', 'appid', 'typeid', 'key', 'flag', 'dataonly', 'titleTemp', 'summaryTemp', 'feedno', 'title', 'summary', 'appiconid', 'clscFold', 'icenter_list_extend', 'abstime', 'feedstime', 'userHome', 'namecardLink', 'ouin', 'uin', 'foldFeed', 'foldFeedTitle', 'showEbtn', 'scope', 'hideExtend', 'nickname', 'emoji', 'remark', 'typevip', 'bitmap', 'yybitmap', 'info_use', 'r_name', 'logimg', 'bor', 'lastFeedBor', 'list_bor2', 'info_user_display', 'upernum', 'oprType', 'moreflag', 'otherflag', 'righ', 'tflag', 'sameuser', 'uper_isfriend', 'uperlist', 'html', 'opuin', 'vip', 'type', 'info_user_name', 'rightflag', 'has_get_key']

with open('data.csv', 'w', encoding='utf-8-sig', newline='') as wf:
    writer = csv.writer(wf)
    writer.writerow(['行为', '发起人昵称', '发起人qq号', '时间', '发起人空间', '有效内容', 'html页面'])

page = 0
while True:
    print(str(page))
    params['offset'] = str(page)
    response = requests.get('https://user.qzone.qq.com/proxy/domain/ic2.qzone.qq.com/cgi-bin/feeds/feeds2_html_pav_all', params=params, cookies=cookies, headers=headers)
    text = response.text
    for i in jsonize_keys: # 所有的key加上双引号
        sub_text = f',{i}:'
        text = re.sub(sub_text, ',"'+sub_text[1:-1]+'":', text)
    for i in jsonize_keys: # 处理特例
        sub_text = '{'+f'{i}:'
        text = re.sub(sub_text, '{"'+sub_text[1:-1]+'":', text)
    text = text.replace('yybitmap:', '"yybitmap":') # 处理特例
    text = text.replace(':true', ':"true"')
    text = text.replace("'", '"') # 所有的values从单引号变成双引号
    text = text.replace(',undefined', '') # 处理特例

    text = text.replace(r'\x22', r'\"')
    text = text.replace(r'\x3C', '<')
    text = text.replace(r'\x27', "'")
    text = text.replace(r'\/', '/')
    
    
    # 掐头去尾
    text = text.replace("""_Callback({
	"code":0,
	"subcode":0,
	"message":"",
	"default":0,
	"data":""", '')
    text = text[1:-4]

    try:
        js = json.loads(text)
    except:
        print('Json解析错误！')
        continue
    has_more = js['main']['hasMoreFeeds']
    for item in js['data']:
        act_type = item['typeid']
        dt = item['feedstime']
        act_qq = item['uin']
        act_home = item['userHome']
        act_name = item['nickname']
        html = item['html'].strip()
        html_xpath = etree.HTML(html)
        comments_list = ''
        extract_text = ' '.join(html_xpath.xpath('//div[contains(@class,"txt-box")]//text()'))

        act_type_name = type_dict.get(act_type, '其它')
        if act_type_name=='回复':
            extract_comments = '\n'.join(html_xpath.xpath('//div[@class="mod-comments"]//text()')) 
            comments_list = extract_comments

        with open('data.csv', 'a', encoding='utf-8-sig', newline='') as wf:
            writer = csv.writer(wf)
            writer.writerow([act_type_name, act_name, act_qq, dt, act_home, extract_text+'\n'+comments_list, html])
        print(extract_text)
        print(act_type_name, act_qq, act_home, act_name, dt)
    if has_more!='true':
        break
    page+=10

