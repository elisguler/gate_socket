#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys 
import time
#import locale
from daemon import Daemon
import socket
from socket import timeout
import ast
import unicodedata
import MySQLdb
import logging
from MySQLdb import IntegrityError
import hashlib

#locale.setlocale(locale.LC_TIME, "tr_TR.UTF-8")

# *********** fonkisyonlar
def utoa(uni):
    return unicodedata.normalize('NFKD', uni).encode('ascii', 'ignore')

def checkHex(raw):
    if raw.upper() != raw:
        return False
    try:
        hexval = int(raw, 16)
        return True
    except:
        return False

def greetingMessage():
    days = ["PZT","SAL","CRS","PER","CUM","CMT","PAZ"]
    message = '^' + time.strftime("%d.%m.%Y ")
    message += days[int(time.strftime("%u"))-1]
    message += time.strftime(" %H:%M") + '^'
    hour = time.localtime(time.time()).tm_hour
    if 0 <= hour < 6:
        message += "IYI GECELER"
    elif 6 <= hour < 13:
        message += "GUNAYDIN"
    elif 13 <= hour < 19:
        message += "IYI GUNLER"
    elif 19 <= hour < 24:
        message += "IYI AKSAMLAR"
    return message + '^'
    
# ***********

def gate_socket_main():
    logger = logging.getLogger('gate_socket')
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    error = logging.FileHandler('/var/socket/log/gate_socket_error.log')
    error.setLevel(logging.ERROR)
    error.setFormatter(formatter)
    logger.addHandler(error)

    warning = logging.FileHandler('/var/socket/log/gate_socket_warning.log')
    warning.setLevel(logging.WARNING)
    warning.setFormatter(formatter)
    logger.addHandler(warning)

    info = logging.FileHandler('/var/socket/log/gate_socket_info.log')
    info.setLevel(logging.INFO)
    info.setFormatter(formatter)
    logger.addHandler(info)

    while True:
        try:
            TCP_IP = '0.0.0.0'
            TCP_PORT = 6000
            BUFFER_SIZE = 1024
            SOCKET_TIMEOUT = 10
            soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            soc.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            soc.bind((TCP_IP, TCP_PORT))
            soc.listen(1)
            logger.info('Server has began listening on: %s - %d', TCP_IP, TCP_PORT)

            while True:
                try:
                    conn, addr = soc.accept()
                    conn.settimeout(SOCKET_TIMEOUT)
                    logger.info('Connection started with: %s', addr)

                    soc_received = conn.recv(BUFFER_SIZE)
                    logger.info('Received: %s', soc_received.rstrip('\r\n'))
                    soc_response = "{"
                    db = MySQLdb.connect(host="localhost",
                                         port=3307,
                                         user="ieeelab",
                                         passwd="ieeelab",
                                         db="gate",
                                         charset='utf8',
                                         use_unicode=True) 
                    dbcur = db.cursor() 
                    if soc_received.startswith("{open"):
                        requested_card = soc_received.split("(")[1].split(")")[0]
                        if not checkHex(requested_card):
                            soc_response += "F|" + greetingMessage() + "^HATA!^KART VERISI^HEX DEGIL"
                        elif dbcur.execute("SELECT person_id, name, surname, enterance_permission, welcome_message FROM persons WHERE BINARY card_data = '%s';" %(requested_card)):
                            db.commit()
                            person = dbcur.fetchall()[0]
                            person_id = person[0]
                            name = utoa(person[1].upper())
                            surname = utoa(person[2].upper())
                            enterance_permission = str(person[3])
                            if (person[4]):
                                welcome_message = utoa(person[4].upper())
                                #splitted = welcome_message.split()
                                # welcome_message = ""
                                # c = 0
                                # for i in splitted:
                                #     i = i[0:20]
                                #     if len(i)+c < 20:
                                #         if c == 0:
                                #             welcome_message += i
                                #             c += len(i)
                                #         else:
                                #             welcome_message += " " + i
                                #             c += len(i) + 1
                                #     else:
                                #         welcome_message += "^" + i
                                #         c = len(i)
                                splitted = welcome_message.split("^")
                                welcome_message = ""
                                for i in splitted:
                                    i = i[0:20]
                                    welcome_message += i + "^"
                                welcome_message = welcome_message[:-1]                                            
                            dbcur.execute("SELECT * FROM gate.enterance_logs WHERE now() < (SELECT MAX(time) from enterance_logs) + interval '10' SECOND order by time desc limit 1;")
                            db.commit()
                            size = dbcur.rowcount
                            if (size == 0):
                                dbcur.execute("INSERT INTO enterance_logs VALUES (NOW(),%s,%s,NULL);" %(person_id, enterance_permission))
                                db.commit()
                            soc_response += enterance_permission + '|' + greetingMessage()
                            if (len(name + ' ' + surname) <= 20):
                                soc_response += name + ' ' + surname + '^'
                            elif (len(name + ' ' + surname) > 20):
                                soc_response += name + '^' + surname + '^'
                            if enterance_permission == '0':
                                soc_response += "YETKISIZ GIRIS^DENEMESI!"
                            elif (person[4]): # eger karsilama verisi varsa
                                soc_response +=  welcome_message
                        else: #unknown card
                            dbcur.execute("SELECT * FROM gate.enterance_logs WHERE now() < (SELECT MAX(time) from enterance_logs) + interval '10' SECOND order by time desc limit 1;")
                            db.commit()
                            size = dbcur.rowcount
                            if (size == 0):
                                dbcur.execute("INSERT INTO enterance_logs VALUES (NOW(),-1,0,'%s');" %(requested_card))
                                db.commit()
                            soc_response += "F|" + greetingMessage() + "TANIMSIZ KART!"
                    elif soc_received.startswith("{add"):
                        requested_card = soc_received.split("(")[1].split(")")[0]
                        if not checkHex(requested_card):
                            soc_response += "F|ERROR CARD NOT HEX"
                        else:
                            dbcur.execute("INSERT INTO new_cards VALUES ('%s',NOW())" %(requested_card))
                            db.commit()
                            soc_response += "SUCCESS"
                    elif soc_received.startswith("{all}"): 
                        dbcur.execute("SELECT name, surname, card_data, enterance_permission FROM persons WHERE card_data IS NOT NULL ORDER BY enterance_permission DESC, name;")
                        db.commit()
                        persons = dbcur.fetchall()
                        for person in persons:
                            name = utoa(person[0].upper())
                            surname = utoa(person[1].upper())
                            card_data = utoa(person[2])
                            enterance_permission = str(person[3])
                            soc_response += '[' + name + ' ' + surname + '|' + card_data + '|' + enterance_permission + ']'
                    elif soc_received.startswith("{list["):
                        dbcur.execute("SELECT name, surname, card_data, enterance_permission FROM persons WHERE card_data IS NOT NULL ORDER BY enterance_permission DESC, name;")
                        db.commit()
                        size = dbcur.rowcount
                        order = int(soc_received.split("[")[1].split("]")[0])
                        if size <= order:
                            soc_response += "F|RANGE ERROR!"
                        else:
                            persons = dbcur.fetchall()
                            person =  persons[order]
                            name = utoa(person[0].upper())
                            surname = utoa(person[1].upper())
                            card_data = person[2]
                            enterance_permission = str(person[3])
                            soc_response += name + ' ' + surname + '|' + card_data + '|' + enterance_permission
                    elif soc_received.startswith("{count}"):
                        dbcur.execute("SELECT COUNT(*) FROM persons WHERE card_data IS NOT NULL;")
                        db.commit()
                        count = str(dbcur.fetchall()[0][0])
                        allList = ""
                        dbcur.execute("SELECT name, surname, card_data, enterance_permission FROM persons WHERE card_data IS NOT NULL ORDER BY enterance_permission DESC, name;")
                        db.commit()
                        persons = dbcur.fetchall()
                        for person in persons:
                            name = utoa(person[0].upper())
                            surname = utoa(person[1].upper())
                            card_data = person[2]
                            enterance_permission = str(person[3])
                            allList += '[' + name + ' ' + surname + '|' + card_data + '|' + enterance_permission + ']'
                        m = hashlib.md5()
                        m.update(allList)
                        soc_response += count + '|' + m.hexdigest()
                    elif soc_received.startswith("{time}"):
                        soc_response += time.strftime("%H:%M:%S/%d-%m-%Y")
                    elif soc_received.startswith("{help}"):
                        soc_response += """
open(CARD_DATA)   : istenilen kart icin kisi bilgisini ve izin bilgisini verir. 
add(NEW_CARD_DATA): yeni kart ekler, kart varsa hata verir, yalnizca hexdecimal buyuk harf karakter kabul eder. 
list[INDEX]       : listenin index sirasindaki elemanini verir, index disiysa hata verir.
all               : tum listeyi verir
count             : listedeki eleman sayisini ve listenin hash bilgisini verir.
time              : guncel tarih ve zamani verir.
"""
                    else:
                        soc_response += "F|WRONG PARAMETER!"
                        logger.warning('Wrong parameter')
                    soc_response += "}"
                except IndexError:
                    soc_response = "{F|MISSING PARAMETER!}"
                    logger.warning('Request cannot handled')
                except socket.timeout:
                    soc_response = "{F|TIMEOUT!}"
                    logger.warning('Timeout error')
                except Exception, e:
                    soc_response = "{F|ERROR!}"
                    logger.error('Unecpected error :' + repr(e))
                finally:
                    soc_response = soc_response.upper()
                    conn.sendall(soc_response)
                    logger.info('Sended: %s', soc_response)
                    logger.info('Connection closed')
                    try:
                        conn.close()
                        dbcur.close()
                        db.close()
                    except Exception, e:
                        pass
        except Exception, e:
            logger.error('Unecpected error: ' + repr(e))
            logger.info('Server will restart')
        finally:
            logger.info('Socket closed')
            soc.close()


# ***********************************servis
class MyDaemon(Daemon):
    def run(self):
        gate_socket_main()

if __name__ == "__main__":
    daemon = MyDaemon('/tmp/gate_socket.pid','/var/socket/log/in.log','/var/socket/log/out.log','/var/socket/log/err.log')
    if len(sys.argv) == 2:
        if 'start' == sys.argv[1]:
            daemon.start()
        elif 'stop' == sys.argv[1]:
            daemon.stop()
        elif 'restart' == sys.argv[1]:
            daemon.restart()
        else:
            print "Unknown command"
            sys.exit(2)
    else:
        print "usage: %s start|stop|restart" % sys.argv[0]
        sys.exit(2)
