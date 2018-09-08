from aip import AipOcr
import threading, time
import  SocketServer
import base64
import struct
import json
# import pymongo
import requests
from pymongo import MongoClient
from ctpnport import *
from newcrnnport import *
import numpy as np
import models.position_helper as POS


import ctypes
import inspect


def _async_raise(tid, exctype):
    """raises the exception, performs cleanup if needed"""
    tid = ctypes.c_long(tid)
    if not inspect.isclass(exctype):
        exctype = type(exctype)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
    if res == 0:
        raise ValueError("invalid thread id")
    elif res != 1:
        # """if it returns a number greater than one, you're in trouble,
        # and you should call it again with exc=NULL to revert the effect"""
        ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
        raise SystemError("PyThreadState_SetAsyncExc failed")
 
def stop_thread(thread):
    _async_raise(thread.ident, SystemExit)

# MyThread.py
class MyThread(threading.Thread):
    def __init__(self, func, args=()):
        super(MyThread, self).__init__()
        self.func = func
        self.args = args
 
    def run(self):
        time.sleep(2)
        self.result = self.func(*self.args)
 
    def get_result(self):
        threading.Thread.join(self) # wait finished
        try:
            return self.result
        except Exception:
            return None


# do the recognization
def api_run(im_raw):
  image = im_raw

  """  """
  client.basicAccurate(image);

  """ optional params """
  options = {}
  options["detect_direction"] = "false"
  options["probability"] = "true"

  """ do the request """
  result = client.basicAccurate(image, options)
  sentence_list = []
  for temp in result['words_result']:
    start = 0
    for word in temp['words']:
      if word == ' ':
        start += 1
      else:
        break
    sentence_list.append(temp['words'][start:])
  return sentence_list

# build the html text
def get_font(res):
  size = str(res.tag_X + 4)
  return "<font size="+size+"> "

# start handle the image
def handle_img(img_raw):
    task = MyThread(api_run, (img_raw,))
    task.start()
    print("start api..")
    img_array = np.fromstring(img_raw,np.uint8)
    img_cv = cv2.imdecode(img_array,cv2.COLOR_BGR2RGB)
    print("start image ctpn..")
    img,text_recs = getCharBlock(text_detector,img_cv)
    print("start image crnn..")
    att = crnnRec(model,converter,img,text_recs)
    sentence_list = task.get_result()
    print(sentence_list)
    for i in range(att.__len__()):
       print(att[i].pred)
       att[i].pred = sentence_list[i]
       att[i].W = att[i].width / sentence_list[i].__len__()
    att_ex = POS.PositionHelper().__sort__(att)
    for i in range(att_ex.__len__()):
       print(get_font(att_ex[i])+ att_ex[i].pred + " </font>")
    # stop_thread(task)

class Myserver(SocketServer.BaseRequestHandler):

    def handle(self):
        conn = self.request
        #conn.sendall(bytes("Start Analysis....",encoding="utf-8"))
        conn.sendall("Start Analysis....")
        total_data = ""
        ret_bytes = conn.recv(4096)
        if ret_bytes:
            if(len(ret_bytes) > 8):
            #TODO: check if the params are valid!
                # check the size , need a try.
                size_user = struct.unpack('i', ret_bytes[0:4])[0]
                size_img = struct.unpack('i', ret_bytes[4:8])[0]
                #TODO: check if the img is too large
                if size_img > 4096 * 1024:
                    conn.sendall("img is too large!!!")
                    return
                total_data = ret_bytes
                checked = False
                # receive all the data
                while len(total_data) < size_user + size_img + 8:
                    ret_bytes = conn.recv(4096)
                    total_data += ret_bytes
                    if not ret_bytes:
                        break
                    # check the user info
                    if len(total_data) > size_user + 8 and not checked:
                        try:
                            raw_user_info = total_data[8:8+size_user]
                            #user_info = json.loads(raw_user_info.decode("utf-8"))
                            user_info = json.loads(raw_user_info)
                            # TODO: check if user is valid
                            try:
                                r = requests.post("http://192.168.17.131/login", user_info)
                                if (r.url == "http://192.168.17.131/campgrounds"):
                                	conn.sendall("Start Analysis..")
                                else:
                                    conn.sendall("permission denied")
                                    return
                            except Exception as e:
                                print(e)
                                raise e
                                return
                            checked = True
                        except Exception as e:
                            #conn.sendall(bytes("error json object",encoding="utf-8"))
                            conn.sendall("error json object")
                            raise e
                            return
                # check the image info
                try:
                    print("start image process..")
                    raw_img = total_data[8+size_user:]
                    img = base64.b64decode(raw_img)
                    handle_img(img)
                    #conn.sendall(bytes("finished!!!",encoding="utf-8"))
                    conn.sendall("finished!!!")
                    # TODO: image analysis
                except Exception as e:
                    #conn.sendall(bytes("error image!",encoding="utf-8"))
                    conn.sendall("error image!")
                    raise e
            else:
                #conn.sendall(bytes("error params!",encoding="utf-8"))
                conn.sendall("error params!")
if __name__ == "__main__":
    # mongodb = MongoClient('localhost',27017)
    # db = mongodb.test
    # users = db.users
    """  APPID AK SK """
    APP_ID = '11765015'
    API_KEY = 'aX3L3UzaL2GTxBHDyCZD4rG6'
    SECRET_KEY = 'kjISzZhXMeLOgnEYB62vdO4gzKvAOgH7'

    client = AipOcr(APP_ID, API_KEY, SECRET_KEY)

    #ctpn
    text_detector = ctpnSource()
    #crnn
    model,converter = crnnSource()

    timer=Timer()
    print("initialize finished...")
    print("Start listening..")
    server = SocketServer.ThreadingTCPServer(("192.168.17.131",50007),Myserver)
    server.serve_forever()