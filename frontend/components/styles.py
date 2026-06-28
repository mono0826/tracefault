"""自定义 CSS 样式"""

import streamlit as st


def custom_css():
    """注入全局自定义 CSS"""
    st.markdown("""
    <style>
    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #f0f2f6;
        border-radius: 4px 4px 0 0;
        padding: 0.5rem 1rem;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #4b9bff;
        color: white;
    }

    /* 控制栏 */
    .settings-bar {
        padding: 10px;
        background-color: #f7f7f7;
        border-radius: 5px;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    /* 源内容 */
    .source-content-container {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 15px;
        margin-top: 10px;
        border: 1px solid #e0e0e0;
    }

    /* 调试头部 */
    .debug-header {
        background-color: #eef2f5;
        padding: 10px 15px;
        border-radius: 5px;
        margin-bottom: 15px;
        border-left: 4px solid #4b9bff;
    }

    /* 按钮悬停 */
    button:hover {
        box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24);
        transition: all 0.3s cubic-bezier(.25,.8,.25,1);
    }

    /* 反馈按钮 */
    .feedback-positive {
        color: #0F9D58;
        font-weight: bold;
    }
    .feedback-negative {
        color: #DB4437;
        font-weight: bold;
    }
    .feedback-given {
        opacity: 0.7;
        font-style: italic;
    }

    /* 处理中提示 */
    .processing-indicator {
        background-color: #fff3cd;
        color: #856404;
        padding: 5px 10px;
        border-radius: 4px;
        border-left: 4px solid #ffeeba;
        margin: 5px 0;
        font-size: 12px;
    }

    /* 迭代轮次 */
    .iteration-round {
        background-color: #f8f9fa;
        border-left: 4px solid #4285F4;
        padding: 10px;
        margin: 10px 0;
        border-radius: 4px;
    }
    .iteration-query {
        background-color: #f0f2f6;
        padding: 8px 12px;
        border-radius: 4px;
        font-family: monospace;
        margin: 5px 0;
    }
    .iteration-info {
        background-color: #e8f5e9;
        padding: 12px;
        border-radius: 4px;
        border-left: 3px solid #4CAF50;
        margin: 10px 0;
    }

    /* 进度条 */
    .iteration-progress {
        height: 8px;
        background-color: #f0f0f0;
        border-radius: 4px;
        margin: 15px 0;
        overflow: hidden;
    }
    .iteration-progress-bar {
        height: 100%;
        background-color: #4CAF50;
        border-radius: 4px;
    }

    /* 示例问题卡片 */
    .example-question {
        background-color: #f7f7f7;
        padding: 8px 12px;
        border-radius: 4px;
        margin: 5px 0;
        cursor: pointer;
        transition: background-color 0.3s;
        font-size: 14px;
    }
    .example-question:hover {
        background-color: #e6e6e6;
    }
    </style>
    """, unsafe_allow_html=True)
