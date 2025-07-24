#!/usr/bin/env python3
"""
SQLite用户管理工具 - 管理员命令行工具
"""
import argparse
import hashlib
import uuid
import sys
import os
from datetime import datetime
from typing import List, Dict

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.database.sqlite_manager import db_manager

class UserAdminTool:
    """用户管理工具"""
    
    def __init__(self):
        self.db = db_manager
    
    def hash_password(self, password: str) -> str:
        """密码哈希"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def create_user(self, name: str, email: str, password: str, role: str = "student"):
        """创建用户"""
        try:
            user_id = str(uuid.uuid4())
            user_data = {
                "id": user_id,
                "name": name,
                "email": email,
                "password": self.hash_password(password),
                "role": role,
                "avatar_url": None
            }
            
            self.db.create_user(user_data)
            print(f"✅ 用户创建成功:")
            print(f"   - ID: {user_id}")
            print(f"   - 姓名: {name}")
            print(f"   - 邮箱: {email}")
            print(f"   - 角色: {role}")
            
        except Exception as e:
            print(f"❌ 用户创建失败: {e}")
    
    def list_users(self):
        """列出所有用户"""
        try:
            users = self.db.get_all_users()
            
            if not users:
                print("❌ 没有找到任何用户")
                return
            
            print(f"📋 用户列表 (共 {len(users)} 个用户):")
            print("-" * 80)
            print(f"{'ID':<36} {'姓名':<15} {'邮箱':<25} {'角色':<10} {'创建时间':<20}")
            print("-" * 80)
            
            for user in users:
                created_at = user['created_at'][:19] if user['created_at'] else 'N/A'
                print(f"{user['id']:<36} {user['name']:<15} {user['email']:<25} {user['role']:<10} {created_at:<20}")
                
        except Exception as e:
            print(f"❌ 获取用户列表失败: {e}")
    
    def get_user_info(self, email: str):
        """获取用户详细信息"""
        try:
            user = self.db.get_user_by_email(email)
            
            if not user:
                print(f"❌ 未找到用户: {email}")
                return
            
            print(f"👤 用户详细信息:")
            print(f"   - ID: {user['id']}")
            print(f"   - 姓名: {user['name']}")
            print(f"   - 邮箱: {user['email']}")
            print(f"   - 角色: {user['role']}")
            print(f"   - 头像: {user['avatar_url'] or '未设置'}")
            print(f"   - 创建时间: {user['created_at']}")
            print(f"   - 更新时间: {user['updated_at']}")
            print(f"   - 是否活跃: {'是' if user['is_active'] else '否'}")
            
            # 获取用户会话信息
            sessions = self.db.get_user_sessions(user['id'])
            print(f"   - 活跃会话: {len(sessions)} 个")
            
            if sessions:
                print(f"   - 会话详情:")
                for i, session in enumerate(sessions[:3], 1):  # 只显示前3个
                    print(f"     {i}. {session['token'][:8]}*** - {session['user_agent'][:30]}...")
                    
        except Exception as e:
            print(f"❌ 获取用户信息失败: {e}")
    
    def delete_user(self, email: str):
        """删除用户"""
        try:
            user = self.db.get_user_by_email(email)
            
            if not user:
                print(f"❌ 未找到用户: {email}")
                return
            
            # 确认删除
            confirm = input(f"⚠️  确定要删除用户 '{user['name']}' ({email}) 吗？(y/N): ")
            if confirm.lower() != 'y':
                print("❌ 取消删除操作")
                return
            
            success = self.db.delete_user(user['id'])
            
            if success:
                print(f"✅ 用户删除成功: {user['name']} ({email})")
            else:
                print(f"❌ 用户删除失败")
                
        except Exception as e:
            print(f"❌ 删除用户失败: {e}")
    
    def update_user_role(self, email: str, new_role: str):
        """更新用户角色"""
        try:
            user = self.db.get_user_by_email(email)
            
            if not user:
                print(f"❌ 未找到用户: {email}")
                return
            
            success = self.db.update_user(user['id'], {"role": new_role})
            
            if success:
                print(f"✅ 用户角色更新成功:")
                print(f"   - 用户: {user['name']} ({email})")
                print(f"   - 原角色: {user['role']}")
                print(f"   - 新角色: {new_role}")
            else:
                print(f"❌ 用户角色更新失败")
                
        except Exception as e:
            print(f"❌ 更新用户角色失败: {e}")
    
    def reset_password(self, email: str, new_password: str):
        """重置用户密码"""
        try:
            user = self.db.get_user_by_email(email)
            
            if not user:
                print(f"❌ 未找到用户: {email}")
                return
            
            # 更新密码（需要直接操作数据库）
            with self.db.get_db_cursor() as cursor:
                cursor.execute('''
                    UPDATE users SET password = ?, updated_at = ? WHERE id = ?
                ''', (self.hash_password(new_password), datetime.now(), user['id']))
            
            print(f"✅ 密码重置成功:")
            print(f"   - 用户: {user['name']} ({email})")
            print(f"   - 新密码: {new_password}")
            print(f"   ⚠️  请提醒用户及时修改密码")
            
        except Exception as e:
            print(f"❌ 密码重置失败: {e}")
    
    def show_stats(self):
        """显示系统统计信息"""
        try:
            stats = self.db.get_database_stats()
            
            print("📊 系统统计信息:")
            print("-" * 40)
            print(f"活跃用户数: {stats.get('active_users', 0)}")
            print(f"总用户数: {stats.get('total_users', 0)}")
            print(f"活跃会话数: {stats.get('active_sessions', 0)}")
            print(f"有效会话数: {stats.get('valid_sessions', 0)}")
            
            role_stats = stats.get('users_by_role', {})
            if role_stats:
                print("\n角色分布:")
                for role, count in role_stats.items():
                    print(f"  - {role}: {count} 个")
                    
        except Exception as e:
            print(f"❌ 获取统计信息失败: {e}")
    
    def cleanup_sessions(self):
        """清理过期会话"""
        try:
            cleaned_count = self.db.cleanup_expired_sessions()
            print(f"✅ 清理过期会话完成: 共清理 {cleaned_count} 个过期会话")
            
        except Exception as e:
            print(f"❌ 清理过期会话失败: {e}")
    
    def list_sessions(self, email: str = None):
        """列出会话信息"""
        try:
            if email:
                # 列出指定用户的会话
                user = self.db.get_user_by_email(email)
                if not user:
                    print(f"❌ 未找到用户: {email}")
                    return
                
                sessions = self.db.get_user_sessions(user['id'])
                print(f"👤 {user['name']} ({email}) 的会话列表:")
            else:
                # 列出所有活跃会话
                with self.db.get_db_cursor() as cursor:
                    cursor.execute('''
                        SELECT s.*, u.name, u.email 
                        FROM user_sessions s 
                        JOIN users u ON s.user_id = u.id 
                        WHERE s.is_active = 1 AND s.expires_at > ? 
                        ORDER BY s.created_at DESC
                    ''', (datetime.now(),))
                    
                    sessions = [dict(row) for row in cursor.fetchall()]
                    
                print(f"🌐 系统活跃会话列表:")
            
            if not sessions:
                print("❌ 没有找到任何活跃会话")
                return
            
            print("-" * 100)
            print(f"{'Token':<12} {'用户':<15} {'设备':<25} {'IP地址':<15} {'创建时间':<20}")
            print("-" * 100)
            
            for session in sessions[:10]:  # 限制显示数量
                token = session['token'][:8] + "***"
                user_name = session.get('name', 'N/A')
                user_agent = (session.get('user_agent', 'Unknown')[:22] + "...") if len(session.get('user_agent', '')) > 25 else session.get('user_agent', 'Unknown')
                ip_addr = session.get('ip_address', 'Unknown')
                created = session['created_at'][:19] if session['created_at'] else 'N/A'
                
                print(f"{token:<12} {user_name:<15} {user_agent:<25} {ip_addr:<15} {created:<20}")
                
        except Exception as e:
            print(f"❌ 获取会话列表失败: {e}")
    
    def create_admin(self, name: str, email: str, password: str):
        """创建管理员账户"""
        print("🔧 创建管理员账户...")
        self.create_user(name, email, password, "admin")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="SQLite用户管理工具")
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 创建用户
    create_parser = subparsers.add_parser('create', help='创建用户')
    create_parser.add_argument('name', help='用户姓名')
    create_parser.add_argument('email', help='用户邮箱')
    create_parser.add_argument('password', help='用户密码')
    create_parser.add_argument('--role', default='student', choices=['admin', 'teacher', 'student'], help='用户角色')
    
    # 创建管理员
    admin_parser = subparsers.add_parser('create-admin', help='创建管理员')
    admin_parser.add_argument('name', help='管理员姓名')
    admin_parser.add_argument('email', help='管理员邮箱')
    admin_parser.add_argument('password', help='管理员密码')
    
    # 列出用户
    subparsers.add_parser('list', help='列出所有用户')
    
    # 用户信息
    info_parser = subparsers.add_parser('info', help='获取用户信息')
    info_parser.add_argument('email', help='用户邮箱')
    
    # 删除用户
    delete_parser = subparsers.add_parser('delete', help='删除用户')
    delete_parser.add_argument('email', help='用户邮箱')
    
    # 更新角色
    role_parser = subparsers.add_parser('set-role', help='更新用户角色')
    role_parser.add_argument('email', help='用户邮箱')
    role_parser.add_argument('role', choices=['admin', 'teacher', 'student'], help='新角色')
    
    # 重置密码
    password_parser = subparsers.add_parser('reset-password', help='重置用户密码')
    password_parser.add_argument('email', help='用户邮箱')
    password_parser.add_argument('password', help='新密码')
    
    # 系统统计
    subparsers.add_parser('stats', help='显示系统统计信息')
    
    # 清理会话
    subparsers.add_parser('cleanup', help='清理过期会话')
    
    # 会话列表
    sessions_parser = subparsers.add_parser('sessions', help='列出会话信息')
    sessions_parser.add_argument('--user', help='指定用户邮箱')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 确保数据库目录存在
    os.makedirs("data/sqlite", exist_ok=True)
    
    tool = UserAdminTool()
    
    try:
        if args.command == 'create':
            tool.create_user(args.name, args.email, args.password, args.role)
        elif args.command == 'create-admin':
            tool.create_admin(args.name, args.email, args.password)
        elif args.command == 'list':
            tool.list_users()
        elif args.command == 'info':
            tool.get_user_info(args.email)
        elif args.command == 'delete':
            tool.delete_user(args.email)
        elif args.command == 'set-role':
            tool.update_user_role(args.email, args.role)
        elif args.command == 'reset-password':
            tool.reset_password(args.email, args.password)
        elif args.command == 'stats':
            tool.show_stats()
        elif args.command == 'cleanup':
            tool.cleanup_sessions()
        elif args.command == 'sessions':
            tool.list_sessions(args.user)
            
    except KeyboardInterrupt:
        print("\n❌ 操作被用户取消")
    except Exception as e:
        print(f"❌ 操作失败: {e}")

if __name__ == "__main__":
    main() 