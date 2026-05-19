"""slowapi limiter 单例。

放在独立模块避免 main / routes 之间的循环导入：
    routes/inspections.py 用 limiter 装饰路由
    main.py 注册 RateLimitExceeded handler + 设 app.state.limiter
两边都从这里 import，main 不直接 import routes（routes 在 include_router 时被加载）。

key_func = get_remote_address: 按客户端 IP 计数；小程序场景下网关 IP 单独算，
本机开发环境用 127.0.0.1（slowapi 默认 in-memory 后端，单进程内累计）。

实际限速值（"10/minute"）写在 routes 装饰器里，对齐 Settings.rate_limit_per_minute。
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
