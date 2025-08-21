# -*- coding: utf-8 -*-
import time
import uuid
import queue
import json
from ws4py.client.threadedclient import WebSocketClient
from ws4py.client.threadedclient import WebSocketBaseClient
import _thread
import AipaasAuth
import threading
import asyncio
import websockets

ws_clients = set()
latest_stream_info = {}
latest_llm_text = ""

async def ws_push_server():
    async def handler(websocket, path):
        ws_clients.add(websocket)
        try:
            if latest_stream_info:
                await websocket.send(json.dumps({"type": "stream", "data": latest_stream_info}))
            while True:
                try:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=0.5)
                    data = json.loads(msg)
                    # 只处理 driverText 类型
                    if data.get("type") == "driverText":
                        driver_text = data.get("data", "")
                        print("收到前端 driverText：", driver_text)
                        if wsclient and hasattr(wsclient, "sendDriverText"):
                            wsclient.sendDriverText(driver_text)
                except asyncio.TimeoutError:
                    pass
        except Exception as e:
            print("ws handler error:", e)
        finally:
            ws_clients.discard(websocket)

    # 启动WebSocket服务并保持运行
    server = await websockets.serve(handler, "0.0.0.0", 8765)
    await server.wait_closed()

def start_ws_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(ws_push_server())

threading.Thread(target=start_ws_server, daemon=True).start()
# threading.Thread(target=lambda: asyncio.run(ws_push_server()), daemon=True).start()

class avatarWebsocket(WebSocketClient, threading.Thread):

    def __init__(self, url, protocols=None, extensions=None, heartbeat_freq=None, ssl_options=None, headers=None,
                 exclude_headers=None, parent=None):
        WebSocketBaseClient.__init__(self, url, protocols=None, extensions=None, heartbeat_freq=None, ssl_options=None,
                                     headers=None, exclude_headers=None)
        threading.Thread.__init__(self)
        self._th = threading.Thread(target=super().run, name='WebSocketClient')
        self._th.daemon = True
        self.appId = ''
        self.sceneId = ''
        self.vcn = ''
        self.anchorId = ''
        self.dataList = queue.Queue(maxsize=100)
        self.status = True
        self.linkConnected = False
        self.avatarLinked = False

    def run(self):
        try:
            self.connect()
            self.connectAvatar()
            _thread.start_new_thread(self.send_Message, ())
            while self.status and not self.terminated:
                self._th.join(timeout=0.1)
        except Exception as e:
            self.status = False
            print(e)

    def stop(self):
        self.status = False
        self.close(code=1000)

    def send_Message(self):
        """
        send msg to server, if no message to send, send ping msg
        :return:
        """
        while self.status:
            if self.linkConnected:
                try:
                    if self.avatarLinked:
                        task = self.dataList.get(block=True, timeout=5)
                        print('%s send msg: %s' % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())), task))
                        self.send(task)
                except queue.Empty:
                    if self.status and self.avatarLinked:
                        self.send(self.getPingMsg())
                    else:
                        time.sleep(0.1)
                except AttributeError:
                    pass
            else:
                time.sleep(0.1)

    def sendDriverText(self, driverText):
        """
        send text msg, interactive_mode default 0
        :param driverText:
        :return:
        """
        try:
            textMsg = {
                "header": {
                    "app_id": self.appId,
                    "request_id": str(uuid.uuid4()),
                    "ctrl": "text_driver",#text_interact
                },
                "parameter": {
                    "nlp": True,
                    "tts": {
                        "vcn": self.vcn,
                        "speed": 50, 
                        "pitch": 50, 
                        "volume": 50,
                    },
                    # "avatar_dispatch": {
                    #     "interactive_mode": 0
                    # },
                    "air":{
                        "air":0,  #是否开启自动动作，0关闭/1开启，自动动作只有开启交互走到大模型时才生效
            #星火大模型会根据语境自动插入动作，且必须是支持动作的形象
                         "add_nonsemantic":0, #是否开启无指向性动作，0关闭，1开启（需配合nlp=true时生效），虚拟人会做没有意图指向性的动作
        }
                },
                "payload": {
                    "text": {
                        "content": driverText
                    }
                }
            }
            self.dataList.put_nowait(json.dumps(textMsg))
        except Exception as e:
            print(e)

    def connectAvatar(self):
        """
        send avatar start Msg
        :return:
        """
        try:
            startMsg = {
                "header": {
                    "app_id": self.appId,
                    "request_id": str(uuid.uuid4()),
                    "ctrl": "start",
                    "scene_id":self.sceneId
                },
                "parameter": {
                    "nlp": True,
                    "tts": {
                        "vcn": self.vcn
                    },
                    "avatar": {
                        "stream": {
                            "protocol": "xrtc",
                            "alpha":1,  # 是否开启透明背景，0关闭/1开启
                        },
                        "avatar_id": self.anchorId
                    }
                }
            }
            print("%s send start request: %s" % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())), json.dumps(startMsg)))
            self.send(json.dumps(startMsg))
        except Exception as e:
            print(e)

    def getPingMsg(self):
        """
        :return: ping msg
        """
        pingMsg = {
            "header": {
                "app_id": self.appId,
                "request_id": str(uuid.uuid4()),
                "ctrl": "ping"
            },
        }
        return json.dumps(pingMsg)

    def opened(self):
        """
        ws connected, msg can be sent
        :return:
        """
        self.linkConnected = True

    def closed(self, code, reason=None):
        msg = 'receive closed, code: ' + str(code)
        print(msg)
        self.status = False

    def received_message(self, message):
        global latest_stream_info, latest_llm_text
        try:
            print(message)
            data = json.loads(str(message))
            if data['header']['code'] != 0:
                self.status = False
                print('receive error msg: %s' % str(message))
            else:
                if 'avatar' in data['payload'] and data['payload']['avatar']['error_code'] == 0 and \
                        data['payload']['avatar']['event_type'] == 'stop':
                    raise BreakException()
                if 'avatar' in data['payload'] and data['payload']['avatar']['event_type'] == 'stream_info':
                    self.avatarLinked = True
                    print('avatar ws connected: %s \n' % str(message))
                    print('stream url: %s \n' % data['payload']['avatar']['stream_url'])
                    latest_stream_info = {
                    "sid": data['payload']['avatar']['cid'],
                    "server": "https://xrtc-cn-east-2.xf-yun.com",
                    "auth": data['payload']['avatar']['stream_extend']['user_sign'],
                    "appid": data['payload']['avatar']['stream_extend']['appid'],
                    "roomId": data['payload']['avatar']['stream_url'].split('/')[-1],
                    "userId": "123123123",
                    "timeStr": str(int(time.time()))
                    }
                    print("推送给前端的stream参数：", latest_stream_info)
                    # 推送给所有前端
                    for ws in list(ws_clients):
                        asyncio.run_coroutine_threadsafe(
                            ws.send(json.dumps({"type": "stream", "data": latest_stream_info})),
                            ws.loop
                        )
                if 'payload' in data and 'nlp' in data['payload'] and 'ttsAnswer' in data['payload']['nlp']:
                    latest_llm_text = data['payload']['nlp']['ttsAnswer']['text']
                    print("大模型输出：", latest_llm_text)
                    # 推送给所有前端
                    for ws in list(ws_clients):
                        asyncio.run_coroutine_threadsafe(
                            ws.send(json.dumps({"type": "llm", "data": latest_llm_text})),
                            ws.loop
                        )
                    # 关键：推送后立即清空，避免重复推送
                    latest_llm_text = ""
                if 'avatar' in data['payload'] and data['payload']['avatar']['event_type'] == 'pong':
                    pass
        except BreakException:
            print('receive error but continue')
        except Exception as e:
            print(e)


class BreakException(Exception):
    """自定义异常类，实现异常退出功能"""
    pass


if __name__ == '__main__':
    url = 'wss://avatar.cn-huadong-1.xf-yun.com/v1/interact'
    appId = '49b9a9cc'
    appKey = '5e1a24ff4fd1ff2ce3088b745fb6c6f8'
    appSecret = 'MTY4YzgyN2YxOWM5N2I0NzA5YTVkNTBj'
    anchorId = '138805001'
    vcn = 'x4_yezi'
    SceneId = "215870166221852672"
    authUrl = AipaasAuth.assemble_auth_url(url, 'GET', appKey, appSecret)
    wsclient = avatarWebsocket(authUrl, protocols='', headers=None)
    try:
        wsclient.appId = appId
        wsclient.anchorId = anchorId
        wsclient.vcn = vcn
        wsclient.sceneId = SceneId
        wsclient.start()
        while wsclient.status and not wsclient.terminated:
            time.sleep(15)
            # text = '请给我一些面试技巧'
            # wsclient.sendDriverText(text)
    except Exception as e:
        print('receive error')
        print(e)
        wsclient.close()

