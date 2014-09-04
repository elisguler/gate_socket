#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys 
import time
from daemon import Daemon
import socket
import ast
import unicodedata
import MySQLdb
import logging
from MySQLdb import IntegrityError
import hashlib

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

# ***********

def gate_socket_main():
    TCP_IP = '0.0.0.0'
    TCP_PORT = 6000
    BUFFER_SIZE = 4096
    SOCKET_TIMEOUT = 300
    soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    soc.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    soc.bind((TCP_IP, TCP_PORT))
    soc.listen(1)

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
    logger.info('Server began listening on: %s - %d', TCP_IP, TCP_PORT)
    
    while True:
        try:
            conn, addr = soc.accept()
            logger.info('Connection started with: %s', addr)
            soc_received = conn.recv(BUFFER_SIZE)
            logger.info('Received: %s', soc_received.rstrip('\r\n'))
            soc_response = "{"
            db = MySQLdb.connect(host="localhost",
                                 user="gate_socket",
                                 passwd="gategate",
                                 db="gate",
                                 charset='utf8',
                                 use_unicode=True) 
            dbcur = db.cursor() 
            if soc_received.startswith("open"):
                requested_card = soc_received.split("(")[1].split(")")[0]
                if not checkHex(requested_card):
                    soc_response = soc_response + "FALSE"
                elif dbcur.execute("SELECT person_id, name, surname, enterance_permission FROM persons WHERE BINARY card_data = '%s';" %(requested_card)):
                    db.commit()
                    person = dbcur.fetchall()[0]
                    person_id = person[0]
                    name = utoa(person[1].upper())
                    surname = utoa(person[2].upper())
                    enterance_permission = str(person[3]) 
                    dbcur.execute("INSERT INTO enterance_logs VALUES (NOW(),%s,%s);" %(person_id, enterance_permission))
                    db.commit()
                    soc_response = soc_response + '|'.join([' '.join([name,surname]),enterance_permission]).encode('ascii', 'ignore')
                else:
                    soc_response = soc_response + "FALSE"
            elif soc_received.startswith("add"):
                requested_card = soc_received.split("(")[1].split(")")[0]
                if not checkHex(requested_card):
                    soc_response = soc_response + "FAIL NOT HEX"
                else:
                    try:
                        if dbcur.execute("SELECT person_id FROM persons WHERE card_data = '%s';" %(requested_card)):
                            db.commit()
                            soc_response = soc_response + "FAIL,DUPLICATE"
                        else:
                            dbcur.execute("INSERT INTO new_cards VALUES ('%s',NOW())" %(requested_card))
                            db.commit()
                            soc_response = soc_response + "SUCCESS"
                    except IntegrityError:
                        soc_response = soc_response + "FAIL DUPLICATE"
            elif soc_received.startswith("all"): # Doesnt work on door circuit 
                dbcur.execute("SELECT name, surname, card_data, enterance_permission FROM persons WHERE card_data IS NOT NULL ORDER BY enterance_permission DESC, name;")
                db.commit()
                persons = dbcur.fetchall()
                for person in persons:
                    name = utoa(person[0].upper())
                    surname = utoa(person[1].upper())
                    card_data = person[2]
                    enterance_permission = str(person[3])
                    soc_response = soc_response + "[" + '|'.join([' '.join([name,surname]),card_data,enterance_permission]).encode('ascii', 'ignore') + "]"
            elif soc_received.startswith("list["):
                dbcur.execute("SELECT name, surname, card_data, enterance_permission FROM persons WHERE card_data IS NOT NULL ORDER BY enterance_permission DESC, name;")
                db.commit()
                size = dbcur.rowcount
                order = int(soc_received.split("[")[1].split("]")[0])
                if size <= order:
                    soc_response = soc_response + "RANGE_ERROR"
                else:
                    persons = dbcur.fetchall()
                    person =  persons[order]
                    name = utoa(person[0].upper())
                    surname = utoa(person[1].upper())
                    card_data = person[2]
                    enterance_permission = str(person[3])
                    soc_response = soc_response + "[" + '|'.join([' '.join([name,surname]),card_data,enterance_permission]).encode('ascii', 'ignore') + "]"
            elif soc_received.startswith("count"):
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
                    allList = allList + "[" + '|'.join([' '.join([name,surname]),card_data,enterance_permission]).encode('ascii', 'ignore') + "]"

                m = hashlib.md5()
                m.update(allList)
                soc_response = soc_response + count + '|' + m.hexdigest()
            elif soc_received.startswith("time"):
                soc_response = soc_response + time.strftime("%H:%M:%S/%d-%m-%Y")
            elif soc_received.startswith("help"):
                soc_response = soc_response +"""
open(CARD_DATA)   : istenilen kart için kişi bilgisini ve izin bilgisini verir. 
add(NEW_CARD_DATA): yeni kart ekler, kart varsa hata verir, yalnızca hexdecimal büyük harf karakter kabul eder. 
list[INDEX]       : listenin indexısirasindakı elemanını verir, index dışıysa hata verir.
all               : tüm listeyi verir
count             : listedeki eleman sayısını ve listenin hash bilgisini verir.
time              : güncel tarih ve zamanı verir.
"""
            else:
                soc_response = soc_response + time.strftime("WRONG PARAMETER")
                logger.warning('Wrong parameter')
            soc_response = soc_response + "}"
            conn.sendall(soc_response)
            logger.info('Sended: %s', soc_response)
        except IndexError:
            soc_response = soc_response + "MISSING PARAMETER}"
            conn.sendall(soc_response)
            logger.error('Request cannot handled')
            logger.info('Sended: %s', soc_response)
            continue
        except:
            soc_response = soc_response + "ERROR}"
            conn.sendall(soc_response)
            logger.error('Unecpected error')
            logger.info('Sended: %s', soc_response)
            continue
        finally:
            logger.info('Connection closed')
            conn.close()
            dbcur.close()
            db.close()


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
