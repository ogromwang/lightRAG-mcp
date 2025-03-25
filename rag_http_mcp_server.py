#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
个性化文档助手 MCP 服务器
可以查询指定电脑路径的文档内容
支持HTTP方式调用RAG服务
"""

import os
import sys
import logging
import asyncio
import requests
import argparse
from typing import List
from pathlib import Path
import mimetypes

try:
    from mcp.server import Server
    from mcp.types import Resource, Tool, TextContent
    from pydantic import AnyUrl
except ImportError as e:
    print(e)
    sys.exit(1)

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("文档助手")

# 从环境变量获取RAG HTTP服务地址和API密钥
def get_rag_http_service_url():
    """从环境变量获取RAG HTTP服务地址和API密钥"""
    parser = argparse.ArgumentParser(description="个性化文档助手 MCP 服务器")
    parser.add_argument('--service-url', type=str, required=True, help="RAG HTTP服务地址，必须提供")
    parser.add_argument('--key', type=str, required=True, help="RAG HTTP服务API密钥，必须提供")
    
    # 解析参数，但不退出程序（仅使用已知参数）
    args, _ = parser.parse_known_args()
    return args.service_url, args.key

# HTTP客户端封装
class RagHttpClient:
    """RAG HTTP客户端"""
    
    def __init__(self, base_url=None, api_key=None):
        """初始化客户端"""
        service_url, key = get_rag_http_service_url()
        self.base_url = base_url or service_url
        self.api_key = api_key or key
        logger.info(f"使用RAG服务地址: {self.base_url}")
    
    def query_naive(self, query: str, top_k: int = 2) -> str:
        """使用naive模式查询"""
        return self.do_query(query, top_k, "naive")
    
    def query_only(self, query: str, top_k: int = 2) -> str:
        """使用only模式查询"""
        return self.do_query(query, top_k, "only", only_need_context=True)
    
    def query_local(self, query: str, top_k: int = 2) -> str:
        """使用local模式查询"""
        return self.do_query(query, top_k, "local")

    def do_query(self, query: str, top_k: int = 2, mode: str = "naive", only_need_context: bool = False) -> str:
        """使用local模式查询"""
        endpoint = f"{self.base_url}/query"
        
        payload = {
            "query": query,
            "mode": mode,
            "only_need_context": only_need_context,
            "only_need_prompt": False,
            "response_type": "string",
            "top_k": top_k,
            "max_token_for_text_unit": 600,
            "max_token_for_global_context": 600,
            "max_token_for_local_context": 600,
            "hl_keywords": [],
            "ll_keywords": [],
            "conversation_history": [],
            "history_turns": 0
        }
        
        headers = {
            'Accept': 'application/json',
            'X-API-Key': self.api_key
        }
        
        try:
            response = requests.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            return result.get("response", "未收到有效回复")
        except Exception as e:
            logger.error(f"查询{mode}模式时出错: {str(e)}")
            return f"查询出错: {str(e)}"
    
    def upload_files(self, file_paths: List[str]) -> str:
        """上传文件到RAG服务"""
        endpoint = f"{self.base_url}/documents/file_batch"
        
        files = []
        for file_path in file_paths:
            path = Path(file_path)
            if not path.exists() or not path.is_file():
                logger.warning(f"文件不存在: {file_path}")
                continue
            
            mime_type = mimetypes.guess_type(path)[0] or 'application/octet-stream'
            files.append(
                ('files', (path.name, open(path, 'rb'), mime_type))
            )
    
        if not files:
            return "没有有效的文件可上传"
        
        headers = {
            'Accept': 'application/json',
            'X-API-Key': self.api_key
        }
        
        try:
            response = requests.post(
                endpoint, 
                files=files,
                headers=headers
            )
            response.raise_for_status()
            result = response.json()
            
            # 关闭所有打开的文件
            for _, (_, file_obj, _) in files:
                file_obj.close()
                
            return f"成功上传 {len(files)} 个文件: {result}"
        except Exception as e:
            # 确保关闭所有打开的文件
            for _, (_, file_obj, _) in files:
                file_obj.close()
                
            logger.error(f"上传文件时出错: {str(e)}")
            return f"上传文件时出错: {str(e)}"

# 全局客户端实例
rag_http_client = None
# 初始化 MCP 服务器
app = Server("document_assistant_mcp")

@app.read_resource()
async def read_resource(uri: AnyUrl) -> str:
    """读取文档资源内容"""
    return ""

@app.list_tools()
async def list_tools() -> list[Tool]:
    """列出可用工具"""
    logger.info("列出工具...")
    return [
        Tool(
            name="query_only",
            description="当需要简单快速的查询知识库的时候，使用HTTP调用RAG服务的only模式进行查询",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "要查询的问题"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="query_naive",
            description="当需要查询知识库简述总结的时候，使用HTTP调用RAG服务的naive模式进行查询",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "要查询的问题"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="query_local",
            description="当需要查询知识库当中的关系图谱的时候，使用HTTP调用RAG服务的local模式进行查询",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "要查询的问题"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="upload_files",
            description="当需要上传文件到知识库的时候，使用HTTP上传文件到RAG服务",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_paths": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "要上传的文件路径列表"
                    }
                },
                "required": ["file_paths"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """执行工具调用"""
    global rag_http_client
    
    logger.info(f"调用工具: {name}, 参数: {arguments}")
    
    try:
        if name == "query_naive":
            query = arguments.get("query")
            if not query:
                raise ValueError("必须提供问题参数")
            
            top_k = arguments.get("top_k", 2)
            if not isinstance(top_k, int) or top_k <= 0:
                raise ValueError("top_k 必须是正整数")
            
            if rag_http_client is None:
                rag_http_client = RagHttpClient()
            
            answer = rag_http_client.query_naive(query, top_k)
            return [TextContent(type="text", text=answer)]
        
        elif name == "query_only":
            query = arguments.get("query")
            if not query:
                raise ValueError("必须提供问题参数")
            
            top_k = arguments.get("top_k", 2)
            if not isinstance(top_k, int) or top_k <= 0:
                raise ValueError("top_k 必须是正整数")
            
            if rag_http_client is None:
                rag_http_client = RagHttpClient()
            
            answer = rag_http_client.query_only(query, top_k)
            return [TextContent(type="text", text=answer)]
        
        elif name == "query_local":
            query = arguments.get("query")
            if not query:
                raise ValueError("必须提供问题参数")
            
            top_k = arguments.get("top_k", 2)
            if not isinstance(top_k, int) or top_k <= 0:
                raise ValueError("top_k 必须是正整数")
            
            if rag_http_client is None:
                rag_http_client = RagHttpClient()
            
            answer = rag_http_client.query_local(query, top_k)
            return [TextContent(type="text", text=answer)]
        
        elif name == "upload_files":
            file_paths = arguments.get("file_paths")
            if not file_paths:
                raise ValueError("必须提供文件路径列表")
            
            if rag_http_client is None:
                rag_http_client = RagHttpClient()
            
            result = rag_http_client.upload_files(file_paths)
            return [TextContent(type="text", text=result)]
        
        else:
            raise ValueError(f"未知工具: {name}")
    except Exception as e:
        logger.error(f"执行工具 {name} 时出错: {str(e)}")
        return [TextContent(type="text", text=f"执行工具时出错: {str(e)}")]

async def main():
    """主函数"""
    from mcp.server.stdio import stdio_server
    
    logger.info("启动文档助手 MCP 服务器...")
    
    # 输出RAG服务地址
    rag_service_url, rag_api_key = get_rag_http_service_url()
    logger.info(f"RAG服务地址: {rag_service_url}")
    
    # 使用标准输入输出作为传输方式
    logger.info("文档助手 MCP 服务器启动成功")
    async with stdio_server() as (read_stream, write_stream):
        try:
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options()
            )
        except Exception as e:
            logger.error(f"服务器错误: {str(e)}", exc_info=True)
            raise

if __name__ == "__main__":
    asyncio.run(main())
