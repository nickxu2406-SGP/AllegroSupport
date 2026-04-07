#!/usr/bin/env python3
"""
邮件采集模块
从 Microsoft Graph API 采集 allegrosupport@culines.com 的邮件
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import argparse

# 第三方库
import requests
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import Json

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('../logs/email_collector.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv('../config/.env')


class GraphAPIClient:
    """Microsoft Graph API 客户端"""
    
    def __init__(self):
        self.tenant_id = os.getenv('GRAPH_TENANT_ID')
        self.client_id = os.getenv('GRAPH_CLIENT_ID')
        self.client_secret = os.getenv('GRAPH_CLIENT_SECRET')
        self.mailbox = os.getenv('MAILBOX', 'allegrosupport@culines.com')
        
        self.access_token = None
        self.token_expires_at = None
        
    def get_access_token(self) -> str:
        """获取访问令牌"""
        if self.access_token and self.token_expires_at:
            if datetime.now() < self.token_expires_at:
                return self.access_token
        
        url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'scope': 'https://graph.microsoft.com/.default',
            'grant_type': 'client_credentials'
        }
        
        response = requests.post(url, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        self.access_token = token_data['access_token']
        self.token_expires_at = datetime.now() + timedelta(seconds=token_data['expires_in'] - 300)
        
        logger.info("成功获取访问令牌")
        return self.access_token
    
    def get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            'Authorization': f'Bearer {self.get_access_token()}',
            'Content-Type': 'application/json'
        }
    
    def get_messages(
        self, 
        days: int = 30, 
        top: int = 100,
        skip: int = 0,
        filter_query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取邮件列表
        
        Args:
            days: 获取最近多少天的邮件
            top: 每次请求返回的邮件数量
            skip: 跳过的邮件数量（分页）
            filter_query: OData 过滤器
        
        Returns:
            邮件列表
        """
        start_date = datetime.now() - timedelta(days=days)
        start_date_str = start_date.strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # 默认过滤器：接收时间 >= start_date
        if not filter_query:
            filter_query = f"receivedDateTime ge {start_date_str}"
        
        url = f"https://graph.microsoft.com/v1.0/users/{self.mailbox}/messages"
        
        params = {
            '$filter': filter_query,
            '$top': top,
            '$skip': skip,
            '$orderby': 'receivedDateTime desc',
            '$select': ','.join([
                'id',
                'conversationId',
                'internetMessageId',
                'subject',
                'from',
                'toRecipients',
                'ccRecipients',
                'receivedDateTime',
                'sentDateTime',
                'body',
                'inReplyTo',
                'internetMessageReferences',
                'hasAttachments',
                'isRead',
                'isDraft',
                'importance',
                'categories'
            ])
        }
        
        response = requests.get(url, headers=self.get_headers(), params=params)
        response.raise_for_status()
        
        data = response.json()
        messages = data.get('value', [])
        
        logger.info(f"获取到 {len(messages)} 封邮件")
        return messages
    
    def get_all_messages(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        获取所有邮件（自动分页）
        """
        all_messages = []
        skip = 0
        top = 100
        
        while True:
            messages = self.get_messages(days=days, top=top, skip=skip)
            if not messages:
                break
            
            all_messages.extend(messages)
            
            if len(messages) < top:
                break
            
            skip += top
        
        logger.info(f"总共获取 {len(all_messages)} 封邮件")
        return all_messages


class EmailProcessor:
    """邮件处理器"""
    
    def __init__(self):
        self.db_connection = self._init_db()
    
    def _init_db(self):
        """初始化数据库连接"""
        return psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '5432'),
            database=os.getenv('DB_NAME', 'allegrosupport_kb'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD')
        )
    
    def parse_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析 Graph API 返回的邮件消息
        转换为数据库存储格式
        """
        parsed = {
            'id': message.get('id'),
            'conversation_id': message.get('conversationId'),
            'internet_message_id': message.get('internetMessageId'),
            'subject': message.get('subject'),
            
            # 发件人
            'sender_email': message.get('from', {}).get('emailAddress', {}).get('address'),
            'sender_name': message.get('from', {}).get('emailAddress', {}).get('name'),
            
            # 收件人
            'recipients': [
                recipient['emailAddress']['address'] 
                for recipient in message.get('toRecipients', [])
            ],
            'cc': [
                recipient['emailAddress']['address'] 
                for recipient in message.get('ccRecipients', [])
            ],
            
            # 时间
            'received_at': self._parse_datetime(message.get('receivedDateTime')),
            'sent_at': self._parse_datetime(message.get('sentDateTime')),
            
            # 内容
            'body_text': message.get('body', {}).get('content'),
            'body_html': message.get('body', {}).get('contentType') == 'html' and message.get('body', {}).get('content'),
            
            # 线程关系
            'in_reply_to': message.get('inReplyTo'),
            'references': message.get('internetMessageReferences'),
            
            # 元数据
            'has_attachments': message.get('hasAttachments', False),
            'is_read': message.get('isRead', False),
            'is_draft': message.get('isDraft', False),
            'importance': message.get('importance'),
            'categories': message.get('categories', []),
        }
        
        return parsed
    
    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """解析 ISO 8601 时间字符串"""
        if not dt_str:
            return None
        
        # Microsoft Graph API 返回格式: 2024-01-01T12:00:00Z
        try:
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        except Exception as e:
            logger.warning(f"解析时间失败: {dt_str}, 错误: {e}")
            return None
    
    def save_to_database(self, email: Dict[str, Any]):
        """保存邮件到数据库"""
        with self.db_connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO emails (
                    id, conversation_id, internet_message_id,
                    subject, sender_email, sender_name,
                    recipients, cc,
                    received_at, sent_at,
                    body_text, body_html,
                    in_reply_to, references,
                    has_attachments, is_read, is_draft,
                    importance, categories,
                    processed_at, processing_status
                ) VALUES (
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    NOW(), 'pending'
                )
                ON CONFLICT (id) DO UPDATE SET
                    processing_status = EXCLUDED.processing_status,
                    updated_at = NOW()
            """, (
                email['id'],
                email['conversation_id'],
                email['internet_message_id'],
                email['subject'],
                email['sender_email'],
                email['sender_name'],
                Json(email['recipients']),
                Json(email['cc']),
                email['received_at'],
                email['sent_at'],
                email['body_text'],
                email['body_html'],
                email['in_reply_to'],
                email['references'],
                email['has_attachments'],
                email['is_read'],
                email['is_draft'],
                email['importance'],
                Json(email['categories'])
            ))
            
            self.db_connection.commit()
            logger.debug(f"保存邮件: {email['id']}")
    
    def close(self):
        """关闭数据库连接"""
        if self.db_connection:
            self.db_connection.close()


def main():
    parser = argparse.ArgumentParser(description='采集 AllegroSupport 邮箱邮件')
    parser.add_argument('--days', type=int, default=30, help='采集最近多少天的邮件')
    parser.add_argument('--dry-run', action='store_true', help='只测试不保存')
    
    args = parser.parse_args()
    
    logger.info(f"开始采集最近 {args.days} 天的邮件")
    
    # 初始化客户端
    graph_client = GraphAPIClient()
    email_processor = EmailProcessor()
    
    try:
        # 获取邮件
        messages = graph_client.get_all_messages(days=args.days)
        
        # 解析并保存
        for i, message in enumerate(messages):
            try:
                parsed = email_processor.parse_message(message)
                
                if not args.dry_run:
                    email_processor.save_to_database(parsed)
                else:
                    logger.info(f"[DRY RUN] 会保存: {parsed['subject']}")
                
                if (i + 1) % 10 == 0:
                    logger.info(f"进度: {i + 1}/{len(messages)}")
            
            except Exception as e:
                logger.error(f"处理邮件失败: {message.get('id')}, 错误: {e}")
        
        logger.info(f"完成！共处理 {len(messages)} 封邮件")
    
    finally:
        email_processor.close()


if __name__ == '__main__':
    main()
