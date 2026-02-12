#!/usr/bin/env python
# coding: utf-8

# In[1]:


import requests
import json
import re
import threading
import time
import os
import streamlit as st
from dotenv import load_dotenv
from duckduckgo_search import DDGS
from colorama import Fore, Style, init
from openai import OpenAI

init(autoreset=True)

# --- 配置 ---
OLLAMA_URL = "http://localhost:11434/v1"
MODEL_A_HOME = "deepseek-r1:1.5b"
MODEL_B_HOME = "qwen3:4b"


# 全局变量，用于线程间通信
user_input_buffer = None
stop_chat = False

# 全局变量，保存聊天记录
# 获取当前脚本所在的文件夹路径
current_dir = os.path.dirname(os.path.abspath(__file__))


# 加载 .env 文件中的变量
load_dotenv()

# 现在可以通过 os.getenv 获取变量了
GLOBAL_API_CONFIG = {
    "api_key": os.getenv("APIKey"),
    "base_url": os.getenv("BASEURL", "https://api.deepseek.com"),
    "model": "deepseek-chat"
}

# --- 1. 初始化状态 ---
if "group_members" not in st.session_state:
    # 初始默认成员，共享上面的全局配置
    st.session_state.group_members = [
        {"name": "Larry"},
        {"name": "Caeson"}
    ]


# In[3]:


import json
import os
from datetime import datetime

def log_conversation(member_name, model, full_prompt, raw_output):

    #将对话记录导出到指定路径：E:\coding\LLM_Chatting

    # 1. 定义目标路径
    # base_dir = r"E:\coding\LLM_Chatting" # 使用 r 前缀防止反斜杠转义
    # log_file = os.path.join(base_dir, "chat_optimization_log.json")
    log_file = os.path.join(current_dir, "chat_optimization_log.json") # 可移植性修改
    
    # 2. 自动创建目录（如果 E:\coding 下没有 LLM_Chatting 文件夹，会自动建一个）
    
    # if not os.path.exists(base_dir):
    #     os.makedirs(base_dir)
    #     print(f"已创建日志目录: {base_dir}")
    

    # 3. 构造单条记录对象
    log_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "member_name": member_name,
        "full_prompt_sent": full_prompt, # 包含 system prompt 和 context 的完整输入
        "raw_response": raw_output       # AI 的原始输出
    }

    # 4. 写入文件（逻辑：如果文件存在则追加，不存在则新建）
    try:
        data = []
        if os.path.exists(log_file):
            with open(log_file, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError: # 防止文件为空或损坏导致崩溃
                    data = []
        
        data.append(log_entry)
        
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            
    except Exception as e:
        print(f"日志写入失败: {e}")


        


# In[4]:


def chat_with_api(member_name, prompt, context_info=""):

    # 统一使用全局 API 配置
    client = OpenAI(
        api_key=GLOBAL_API_CONFIG["api_key"],
        base_url=GLOBAL_API_CONFIG["base_url"]
    )
    
    # 动态获取当前群里所有人的名字
    all_names = [m['name'] for m in st.session_state.group_members]
    other_members = [n for n in all_names if n != member_name]
    
    

    # 2. 构造 System Prompt (前两行写死，规则部分调用 session_state)
    system_message = (
        f"你现在是一个群聊中的成员，你的名字是【{member_name}】，你只作为{member_name}发言。\n"
        f"群里还有其他成员：{'、'.join(other_members)},你们能彼此看到，不用强调自己的身份。\n"
        "规则：\n"
        f"{st.session_state.custom_rules}" # 这里动态插入你修改的规则
    )

    full_prompt = f"参考背景：{context_info}\n\n先前的聊天内容{prompt}"
    try:
        response = client.chat.completions.create(
            model=GLOBAL_API_CONFIG["model"],
            messages=[
                {"role": "system", "content": system_message}, # 身份烙印
                {"role": "user", "content": f"参考资料：{context_info}\n\n对话流：{prompt}"}
            ],
            stream=False
        )
        raw_content = response.choices[0].message.content
        # --- 核心修改：导出数据 ---
        log_conversation(
            member_name,
            GLOBAL_API_CONFIG["model"],
            full_prompt, 
            raw_content
        )
        # ------------------------
        return response.choices[0].message.content
    except Exception as e:
        return f"接口调用失败: {str(e)}"
    


# In[7]:



import time

# --- 1. 初始化状态 ---
if "running" not in st.session_state:
    st.session_state.running = False
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "web_data" not in st.session_state:
    st.session_state.web_data = ""

# --- 2. 侧边栏控制面板 ---
with st.sidebar:
    st.header("控制中心")
    
    # 开始/停止按钮逻辑
    if not st.session_state.running:
        if st.button("🚀 开始自动对谈"):
            st.session_state.running = True
            st.rerun()
    else:
        if st.button("🛑 暂停对话"):
            st.session_state.running = False
            st.rerun()

    if st.button("🗑️ 清空记录"):
        st.session_state.chat_history = []
        st.session_state.running = False
        st.rerun()


    st.header("👥 成员管理")
    
    # 添加新成员只需输入名字
    new_name = st.text_input("新增成员姓名", placeholder="输入名字后点确认...")
    if st.button("➕ 确认添加"):
        if new_name:
            # 检查重名
            if any(m['name'] == new_name for m in st.session_state.group_members):
                st.warning("名字重复啦！")
            else:
                st.session_state.group_members.append({"name": new_name})
                st.success(f"已邀请 {new_name} 入群")
                st.rerun()
    
    st.divider()
    
    # 显示并允许删除成员
    st.subheader("当前成员列表")
    for i, m in enumerate(st.session_state.group_members):
        col1, col2 = st.columns([4, 1])
        col1.write(f"🎭 **{m['name']}**")
        if col2.button("🗑️", key=f"del_{i}"):
            st.session_state.group_members.pop(i)
            st.rerun()

# 添加功能：system message部分自定义
# 默认规则常量
DEFAULT_RULES = """此外，群中还有群主Admin。
1. 这是一个实时讨论，请根据大家的聊天记录进行回应。
2. 你可以直接点名回应某人，也可以发表独立见解。
3. 保持对话自然，不要总是复述别人的话。
4. 每次发言尽量自然，使聊天内容自然延续。
5. 如果Admin提出了一项任务或指令，请优先回应他。"""

# 初始化 session_state
if "custom_rules" not in st.session_state:
    st.session_state.custom_rules = DEFAULT_RULES
with st.sidebar:
    st.header("📜 群聊规则配置")
    
    # 规则编辑框
    st.session_state.custom_rules = st.text_area(
        "自定义 AI 行为规则：", 
        value=st.session_state.custom_rules, 
        height=200
    )
    
    # 重置按钮
    if st.button("🔄 重置为默认规则(请先Rerun)"):
        st.session_state.custom_rules = DEFAULT_RULES
        st.rerun()

# --- 3. 聊天内容渲染展示 ---
st.title("🤖 chatbots群聊")

# 渲染历史记录（增加健壮性检查，防止旧数据报错）
for msg in st.session_state.chat_history:
    if isinstance(msg, dict): # 只渲染字典格式的消息
        with st.chat_message(msg["role"], avatar="🦊"):
            st.write(f"**{msg['name']}**：{msg['content']}")

# --- [核心逻辑] 响应用户输入 (必须放在循环逻辑之前) ---
if user_prompt := st.chat_input("输入信息..."):
    # 1. 构造字典格式的消息
    new_admin_msg = {
        "role": "user", 
        "name": "Admin", 
        "content": user_prompt
    }
    # 2. 存入历史记录
    st.session_state.chat_history.append(new_admin_msg)
    # 3. 确保输入后维持运行状态（或者设置为True让它动起来）
    st.session_state.running = True
    # 4. 刷新页面，让 Admin 的话先显示出来
    st.rerun() 

# --- 4. 自动聊天循环逻辑 ---
if st.session_state.running:
    # 每一轮对谈
    for member in st.session_state.group_members:
        
        # 在这里也可以加一个简单的检查，防止模型复读或出错
        current_name = member['name']
        with st.chat_message("assistant", avatar="🦊"):
            with st.spinner(f"{member['name']} 正在输入..."):
                # 构造上下文（只取字典格式的内容）
                context_list = []
                for m in st.session_state.chat_history[-10:]:
                    if isinstance(m, dict):
                        context_list.append(f"{m['name']}: {m['content']}")
                
                full_context = "\n".join(context_list)
                reply = chat_with_api(current_name, full_context, st.session_state.web_data)   # st.session_state.web_data是联网搜索功能预留接口
                
                # 存储并显示
                new_msg = {"role": "assistant", "name": member['name'], "content": reply}
                st.session_state.chat_history.append(new_msg)
                st.write(f"**{member['name']}**: {reply}")
                
                time.sleep(2)
    
    # 关键：一轮结束后自动开启下一轮
    st.rerun()


# 添加功能：历史记录查询

import pandas as pd

with st.sidebar:
    st.divider()
    if st.checkbox("📜 查看往期日志分析"):
        # log_path = r"E:\coding\LLM_Chatting\chat_optimization_log.json"
        log_path = os.path.join(current_dir, "chat_optimization_log.json")  # 可移植性修改
        
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                logs = json.load(f)
            
            # 使用表格形式快速浏览关键信息
            df = pd.DataFrame(logs)
            if not df.empty:
                # 只显示时间、成员和回复简述
                st.dataframe(df[['timestamp', 'member_name', 'raw_response']])
                
                # 允许选择某一条详细查看
                selected_index = st.number_input("输入索引查看完整对话详情", 0, len(logs)-1, 0)
                st.info(f"**提示词原文：**\n{logs[selected_index]['full_prompt_sent']}")
                st.success(f"**AI 原始回复：**\n{logs[selected_index]['raw_response']}")
        else:
            st.warning("暂无日志文件")



