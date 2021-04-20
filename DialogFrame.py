#!/usr/bin/env python
# coding: utf-8

"""DialogFrame

対話劇作成フレームワーク。

========================================
バージョン0.21(2016-08-06)
    完成。
バージョン1.0(2017-09-25)
    久々に開いてdocとか書いた。
    macで開くためにマウス操作に対応。
        左クリック: ページ送り
        スクロールボタン: 「いつでも画像」の表示
        右クリック: ページ戻り
        上スクロール: ヘルプ
        下スクロール: 下キー
    およびmacでのBGM再生を無効にした。
"""

import sys
import os
import traceback
import pygame
import datetime
import random
import sqlite3
import json
from pygame.locals import *
from html.parser import HTMLParser
from DialogFrameConfig import Conf
import accept_mouse_click

# ショートカットからの実行だったらカレントディレクトリをexeのあるディレクトリに移す。
# NOTE: のちのち、「ショートカット実行ではないのにカレントディレクトリを移してしまう」という事態が発生し
#       混乱を招いた。もし次に発生した際に、気付けるように、 print しておく。
#       なお、このときの事態は、カセット repository のほうに log フォルダが入っていなかったことが原因だった。
for d in ['image', 'log', 'maintext', 'other', 'sound']:
    if not os.path.exists(Conf.cassette+os.sep+d):
        os.chdir(os.path.dirname(sys.executable))
        print('NOTE: ショートカットからの実行であると判断され、カレントディレクトリが移されました。')
        break


class FrameResources:
    """ダイアログプレイに使うリソース(メインテキスト、画像、音楽)を各ディクショナリで管理するクラス。
    これをインスタンス化して実際に使う。
    property
        textList
        imageDic
        soundDic
        bgm
    """

    def __init__(self):
        """全リソースを取得する。"""
        # メインテキストがリストで指示されてるときは、オープニングの段階では読まない
        if str(type(Conf.maintextName)) != "<class 'str'>":
            self.textList = False
        else:
            self.textList = self.createTextList()
        self.imageDic = self.createImageDic()
        self.soundDic = self.createSoundDic()
        self.bgm = self.createBGM()

    def exportJson(self):
        """現在のFrameResourcesインスタンスの状態をJSONで出力する。"""
        imageInstances = {}
        for key,instance in self.imageDic.items():
            imageInstances[key] = {}
            imageInstances[key]['xy'] = instance.xy
        soundInstances = {}
        for key,instance in self.soundDic.items():
            soundInstances[key] = {}
            soundInstances[key]['vol'] = instance.vol
        bgmDic = {
            'name': self.bgm.name,
            'vol': self.bgm.vol,
            'put': self.bgm.put,
        }
        data = {
            'imageInstances': imageInstances,
            'soundInstances': soundInstances,
            'bgmDic': bgmDic,
        }
        return json.dumps(data)

    def importJson(self, jsondata):
        """受け取ったjsonデータを自分自身に反映させる。"""
        data = json.loads(jsondata)
        for key,dic in data['imageInstances'].items():
            self.imageDic[key].xy = dic['xy']
        for key,dic in data['soundInstances'].items():
            self.soundDic[key].vol = float(dic['vol'])
        self.bgm.name = data['bgmDic']['name']
        self.bgm.vol = float(data['bgmDic']['vol'])
        self.bgm.put = bool(data['bgmDic']['put'])

    def createTextList(self, maintextName=False):
        """メインテキストを1パラグラフごとのリストにする。"""
        # maintextNameがわざわざ指示されるのはmaintextが複数あるとき
        if maintextName == False:
            filename = Conf.maintextName
        else:
            filename = maintextName
        # encodingがどれかわからんので総当りでヒットしたやつでtextを作る
        for enc in ('utf-8', 'sjis', 'euc-jp', 'ascii'):
            try:
                with open(Conf.cassette+os.sep+'maintext'+os.sep+filename, 'r', encoding=enc) as f:
                    text = f.read()
                    break
            except:
                pass
        return text.split('\n\n')

    def createImageDic(self):
        """Imagesインスタンスの入ったディクショナリを作る。"""
        imageDic = {}
        for image in Conf.imageConf:
            imageDic[image['name']] = Images(Conf.cassette+os.sep+'image'+os.sep+image['name'], image['trans'])
        return imageDic

    def createSoundDic(self):
        """Soundsインスタンスの入ったディクショナリを作る"""
        soundDic = {}
        for sound in Conf.seConf:
            soundDic[sound['name']] = Sounds(Conf.cassette+os.sep+'sound'+os.sep+sound['name'])
        return soundDic

    def createBGM(self):
        """BGMインスタンスを作る"""
        return BGMs()

    def resetSound(self):
        """SoundDicの中のSoundsインスタンスplayプロパティを全部Falseにする。"""
        for sound in Conf.seConf:
            self.soundDic[sound['name']].put = False


class Images:
    """画像のサーフィスと座標をもつクラス。
    property
        surface サーフィス
        xy 座標
    """

    def __init__(self, imagePath, transparence=False):
        self.surface = self.createSurface(imagePath, transparence)
        self.xy = [0, 0]
        # 画像の表示状態をimageOrderリストで管理するようになったら必要なくなった
        # self.put = False

    def createSurface(self, imagePath, transparence):
        """画像サーフィスを作成する。"""
        if transparence == False:
            return pygame.image.load(imagePath).convert_alpha()
        else:
            surface = pygame.image.load(imagePath).convert_alpha()
            surface.set_colorkey(surface.get_at(transparence), RLEACCEL)
            return surface

    def blit(self):
        """画面にblitする。"""
        return screen.blit(self.surface, self.xy)


class Sounds:
    """音声のサーフィス(?)をもつクラス。
    property
        surface サーフィス
        vol 音量
        play 再生済みならTrue
    """

    def __init__(self, soundPath):
        self.surface = pygame.mixer.Sound(soundPath)
        self.vol = 0.1
        self.volume(0.1)
        self.put = False

    def volume(self, num):
        """音量を設定しつつ変える。"""
        self.vol = float(num)
        self.surface.set_volume(float(num))

    def play(self):
        """再生する。Trueになったself.putはturnPageと共に戻る。"""
        self.put = True
        return self.surface.play()


class BGMs:
    """再生中のBGMファイル名、音量、状態をもつクラス。インスタンスは一個だけ生成する。
    property
        name ファイル名
        vol 音量(0.0~1.0)
        play 流れてる状態かどうか
    """

    def __init__(self):
        self.name = ''
        self.vol = 0.1
        self.volume(0.1)
        self.put = False

    def change(self, name):
        # macではmp3が読めないし、いっそBGM再生はナシにする。
        if not sys.platform.startswith('win'):
            return None
        self.name = name
        pygame.mixer.music.load(Conf.cassette+os.sep+'sound'+os.sep+name)

    def volume(self, num):
        if not sys.platform.startswith('win'):
            return None
        self.vol = float(0.1)
        pygame.mixer.music.set_volume(float(num))

    def play(self):
        if not sys.platform.startswith('win'):
            return None
        # 同じファイル名がすでに再生中だったらスキップ
        self.put = True
        pygame.mixer.music.play(-1)

    def stop(self):
        if not sys.platform.startswith('win'):
            return None
        self.put = False
        pygame.mixer.music.stop()


class TagParse(HTMLParser):
    """htmlタグをパースするためのクラス。インスタンス.feed(タグ文字列)で使う。
    property
        dic
    """

    def handle_starttag(self, tag, attrs):
        """feedするとdicにパースしたタグが入る。"""
        self.dic = dict(attrs)


class DialogFrame:
    """ダイアログプレイを起動するクラス。"""

    def __init__(self):
        """DialogFrameクラス全体通して使う__rsrc,__statusパラメータの定義。"""
        self.__rsrc = FrameResources()
        self.__status = {
            'default': {
                'mode':'opening' if Conf.useOpening else 'dialog',
                'page':0,'imageOrder':[],'num':0,'num2':0,'message':'','frameNum':0,
            },
            'mode': 'opening' if Conf.useOpening else 'dialog',
            'page': 0,
            # 現在表示している画像のblit順序を保存しておく
            'imageOrder': [],
            # ページ送りごとに初期値に戻る汎用プロパティ ダイスロールのときに使ったりする
            'num': 0,
            'num2': 0,
            'message': '',
            # アニメーションのためのフレーム数
            'frameNum': 0,
            # ページ戻りモードのとき使用。「何ページ戻ったか」
            'pageBack': 0,
        }

    def main(self):
        """ゲームループのあるメソッド。"""

        while True:
            screen.fill((0,0,0))

            # いつでも画像オープンが有効なら、imageOrderの一番最後に該当ファイルを追加
            if self.__status['num2'] == 1:
                self.__status['imageOrder'].append(Conf.imageOpenName)

            # 表示状態の画像を順番にブリる
            for imagename in self.__status['imageOrder']:
                screen.blit(self.__rsrc.imageDic[imagename].surface,
                    tuple(self.__rsrc.imageDic[imagename].xy))

            # 他の処理に絡まないように、画像blitが終わったら「いつでも画像」は消す
            if self.__status['num2'] == 1:
                del self.__status['imageOrder'][len(self.__status['imageOrder'])-1]

            if self.__status['mode'].endswith('__announce'):
                self.announceMode()
                self.showHelp()
            if self.__status['mode'].endswith('__back'):
                self.backMode()
            if self.__status['mode'] == 'opening':
                # maintextがいっこのときと複数のときで分岐
                if str(type(Conf.maintextName)) != "<class 'str'>":
                    self.openingMode2()
                else:
                    self.openingMode()
            if self.__status['mode'] == 'dialog':
                self.dialogMode()
                self.showHelp()

            pygame.display.update()
            clock.tick(framerate)
            # 特に理由があって0に戻すわけじゃない。なんとなくそのほうがいいかなって思うだけ。
            self.__status['frameNum'] = (self.__status['frameNum'] + 1
                if self.__status['frameNum'] < 1800 else 0)

    def showHelp(self):
        """dialogモードで、「ヘルプ:F11」みたいな表示を表示。"""
        padding = 3
        font = pygame.font.Font(Conf.cassette+os.sep+'other'+os.sep+Conf.dialogFont, 11)
        if self.__status['mode'].endswith('__announce'):
            textSize = font.size(Conf.keyConf['turnPage'] + 'キーで閉じる')
        else:
            textSize = font.size('ヘルプ:' + Conf.keyConf['showHelp'])
        if   Conf.helpConf['location'] in 'nw':
            location = (padding*2, padding*2)
        elif Conf.helpConf['location'] in 'ne':
            location = (640-padding*2-textSize[0], padding*2)
        elif Conf.helpConf['location'] in 'sw':
            location = (padding*2, 480-padding*2-textSize[1])
        elif Conf.helpConf['location'] in 'se':
            location = (640-padding*2-textSize[0], 480-padding*2-textSize[1])
        pygame.draw.rect(screen, Conf.helpConf['boxColor'],
            Rect(location[0]-padding,location[1]-padding,textSize[0]+padding*2,textSize[1]+padding*2))
        if self.__status['mode'].endswith('__announce'):
            text = font.render(Conf.keyConf['turnPage'] + 'キーで閉じる', True, Conf.helpConf['mesColor'])
        else:
            text = font.render('ヘルプ:' + Conf.keyConf['showHelp'], True, Conf.helpConf['mesColor'])
        screen.blit(text, location)

    def announceMode(self):
        """アナウンスモードのときゲームループに差し込まれるメソッド。
        セーブとかロードの通知に使う。"""
        # 一行だけ(str)と二行以上(list)で分岐
        if str(type(self.__status['message'])) == "<class 'str'>":
            # テキストのサイズを取得して、それに見合ったサイズのrectを作る
            textSize = font.size(self.__status['message'])
            pygame.draw.rect(screen, Conf.announceConf['boxColor'],
                Rect(50,50,textSize[0]+20, textSize[1]+20))
            text = font.render(self.__status['message'], True, Conf.announceConf['mesColor'])
            screen.blit(text, (60,60))
        if str(type(self.__status['message'])) == "<class 'list'>":
            textLineNum = 0
            # メッセージボックスの大きさを求める (一番長い行の幅+20, フォントの高さ*行数+20)
            width = 0
            for line in self.__status['message']:
                textSize = font.size(line)
                width = textSize[0] if width < textSize[0] else width
            width = width + 20
            height = textSize[1] * len(self.__status['message']) + 20
            pygame.draw.rect(screen, Conf.announceConf['boxColor'],
                Rect(50,50+font.get_linesize()*textLineNum,width, height))
            for line in self.__status['message']:
                text = font.render(line, True, Conf.dialogColor)
                screen.blit(text, (60,60+font.get_linesize()*textLineNum))
                textLineNum += 1

        for event in pygame.event.get():

            event = self.swicth_mouse_click(event)

            if event.type == QUIT:
                sys.exit()
            if event.type == KEYDOWN:
                if event.key == K_F4 and bool(event.mod and KMOD_ALT):
                    sys.exit()
                if event.key == keyConf['turnPage'] or event.key == K_RETURN:
                    self.__status['mode'] = self.__status['mode'].rstrip('__announce')

    def openingMode(self):
        """オープニングモードのときゲームループに差し込まれるメソッド。"""
        # Confの設定からオープニング用のtextListを作る
        # line0: 土台表示
        # line1: 「はじめから」選択中
        # line2: 「つづきから」選択中
        line0  = ('<event name=image removeall>\n')
        line0 += ('<event name=image file="%s" x=0 y=0 put>\n'
            % Conf.openingBackGroundImage)
        line0 += ('<event name=bgm file="%s" volume=%s play>\n'
            % (Conf.openingBGM['name'], Conf.openingBGM['volume']))
        line0 += ('<event name=image file="%s" x=%s y=%s put>\n'
            % (Conf.openingStart['name1'], Conf.openingStart['x'], Conf.openingStart['y']))
        line0 += ('<event name=image file="%s" x=%s y=%s put>\n'
            % (Conf.openingContinue['name1'], Conf.openingContinue['x'], Conf.openingContinue['y']))
        line0 += '<event name=skip>'

        line1  = ('<event name=image file="%s" remove>\n'
            % Conf.openingContinue['name2'])
        line1 += ('<event name=image file="%s" x=%s y=%s shake=%s put>'
            % (Conf.openingStart['name2'], Conf.openingStart['x'],
                Conf.openingStart['y'], Conf.openingStart['shake']))

        line2  = ('<event name=image file="%s" remove>\n'
            % Conf.openingStart['name2'])
        line2 += ('<event name=image file="%s" x=%s y=%s shake=%s put>'
            % (Conf.openingContinue['name2'], Conf.openingContinue['x'],
                Conf.openingContinue['y'], Conf.openingContinue['shake']))

        textList = [line0, line1, line2]
        draft = textList[self.__status['page']]
        lineList = draft.split('\n')

        for line in lineList:
            if (line.startswith('<event ') and line.endswith('>')):
                # タグ行ならタグ種類に合わせた処理へ
                self.dialogEvent(line)

        for event in pygame.event.get():

            event = self.swicth_mouse_click(event)

            if event.type == QUIT:
                sys.exit()
            if event.type == KEYDOWN:
                if event.key == K_F4 and bool(event.mod and KMOD_ALT):
                    sys.exit()

                # 0がはじめから、1がつづきからとする
                page = self.__status['page']
                if event.key == K_UP:
                    self.__status['page'] = 1 if page == 2 else 2
                if event.key == K_DOWN:
                    self.__status['page'] = 2 if page == 1 else 1
                if event.key == K_LEFT:
                    self.__status['page'] = 1 if page == 2 else 2
                if event.key == K_RIGHT:
                    self.__status['page'] = 2 if page == 1 else 1
                if event.key == keyConf['turnPage'] or event.key == K_RETURN:
                    if page == 1:
                        self.__status['mode'] = 'dialog'
                        self.__status['page'] = 0
                        self.__rsrc.soundDic[Conf.openingSound['name']].volume(Conf.openingSound['volume'])
                        self.__rsrc.soundDic[Conf.openingSound['name']].play()
                        self.__rsrc.resetSound()
                    else:
                        # セーブ機能がない場合はメッセージだけ出す
                        if Conf.useSave:
                            self.loadData(1)
                        else:
                            self.__status['message'] = 'This dialog doesn\'t allow loading data.'
                            self.__status['mode'] = self.__status['mode'] + '__announce'

    def openingMode2(self):
        """メインテキストがふたつ以上あるときのオープニング。
        openingStartListのぶんだけ選択肢を作り、選択中のインデックス番号をmaintextのリストから取り出して読む。
        """
        # name2を全消しするタグを作っとく
        removeName2 = ''
        for openingStart in Conf.openingStartList:
            removeName2 += ('<event name=image file="%s" remove>\n'
                % openingStart['name2'])

        textList = []
        for i in range(len(Conf.openingStartList) + 1):
            # +1は土台のぶん
            if i == 0:
                line  = '<event name=image removeall>\n'
                line += ('<event name=image file="%s" x=0 y=0 put>\n'
                    % Conf.openingBackGroundImage)
                line += ('<event name=bgm file="%s" volume=%s play>\n'
                    % (Conf.openingBGM['name'], Conf.openingBGM['volume']))
                for openingStart in Conf.openingStartList:
                    line += ('<event name=image file="%s" x=%s y=%s put>\n'
                        % (openingStart['name1'], openingStart['x'], openingStart['y']))
                line += '<event name=skip>'
            else:
                line += removeName2
                line += ('<event name=image file="%s" x=%s y=%s shake=%s put>'
                    % (Conf.openingStartList[i-1]['name2'], Conf.openingStartList[i-1]['x'],
                        Conf.openingStartList[i-1]['y'], Conf.openingStartList[i-1]['shake']))
            textList.append(line)
        draft = textList[self.__status['page']]
        lineList = draft.split('\n')

        for line in lineList:
            if (line.startswith('<event ') and line.endswith('>')):
                # タグ行ならタグ種類に合わせた処理へ
                self.dialogEvent(line)

        for event in pygame.event.get():

            event = self.swicth_mouse_click(event)

            if event.type == QUIT:
                sys.exit()
            if event.type == KEYDOWN:
                if event.key == K_F4 and bool(event.mod and KMOD_ALT):
                    sys.exit()

                # page番号が現在選択中のtextlistインデックスであり、maintextインデックス+1
                # +1は土台のぶん。textlist==1のとき選択中なのはmaintext[0]
                page = self.__status['page']
                if event.key == K_UP:
                    self.__status['page'] = page-1 if page!=1 else len(Conf.openingStartList)
                if event.key == K_DOWN:
                    self.__status['page'] = page+1 if page!=len(Conf.openingStartList) else 1
                if event.key == K_LEFT:
                    self.__status['page'] = page-1 if page!=1 else len(Conf.openingStartList)
                if event.key == K_RIGHT:
                    self.__status['page'] = page+1 if page!=len(Conf.openingStartList) else 1
                if event.key == keyConf['turnPage'] or event.key == K_RETURN:
                    # page番号-1のmaintextをロードしてdialogModeへGO
                    self.__rsrc.textList = self.__rsrc.createTextList(Conf.maintextName[self.__status['page'] - 1])
                    self.__status['mode'] = 'dialog'
                    self.__status['page'] = 0
                    self.__rsrc.soundDic[Conf.openingSound['name']].volume(Conf.openingSound['volume'])
                    self.__rsrc.soundDic[Conf.openingSound['name']].play()
                    self.__rsrc.resetSound()

    def dialogMode(self):
        """本編モードのときゲームループに差し込まれるメソッド。"""
        draft = self.__rsrc.textList[self.__status['page']]
        lineList = draft.split('\n')
        # テキスト行をblitするたびに増える数値(=改行の数)
        textLineNum = 0
        # パラグラフ全体に関連付け画像のキーがあるかどうか
        linkingKeyList = []
        for line in lineList:
            if (line.startswith('<event ') and line.endswith('>')):
                # タグ行ならタグ種類に合わせた処理へ
                self.dialogEvent(line)
            elif line.startswith('#'):
                # コメント欄は無視
                pass
            else:
                # 関連付け画像のキー検索
                for linkingDic in Conf.linkingList:
                    for key in linkingDic:
                        if key in line:
                            linkingKeyList.append(key)

                # テキスト行なら一行ずつblitへ
                text = font.render(line, True, Conf.dialogColor)
                screen.blit(text, (Conf.dialogX, Conf.dialogY+font.get_linesize()*textLineNum))
                textLineNum += 1

        # キーがリストに入ってたらmainをブリって、入ってなけりゃbackをブリる
        for linkingDic in Conf.linkingList:
            for key,dic in linkingDic.items():
                if key in linkingKeyList:
                    if dic['back'] in self.__status['imageOrder']:
                        # backがある -> mainと交換
                        targetIndex = self.__status['imageOrder'].index(dic['back'])
                        self.__status['imageOrder'][targetIndex] = dic['main']
                        # 座標も同じにする
                        self.__rsrc.imageDic[dic['main']].xy = self.__rsrc.imageDic[dic['back']].xy
                    else:
                        # mainがあるかどっちもない
                        pass
                else:
                    if dic['main'] in self.__status['imageOrder']:
                        # mainがある -> backと交換
                        targetIndex = self.__status['imageOrder'].index(dic['main'])
                        self.__status['imageOrder'][targetIndex] = dic['back']
                        # 座標も同じにする
                        self.__rsrc.imageDic[dic['back']].xy = self.__rsrc.imageDic[dic['main']].xy
                    else:
                        # backがあるかどっちもない
                        pass

        for event in pygame.event.get():

            event = self.swicth_mouse_click(event)

            if event.type == QUIT:
                sys.exit()
            if event.type == KEYDOWN:
                if event.key == K_F4 and bool(event.mod and KMOD_ALT):
                    sys.exit()

                # いつでも画像オープン中はその画像を消す以外の行動はできない
                if self.__status['num2'] == 1:
                    if event.key == keyConf['imageOpen'] and Conf.imageOpenName:
                        self.__status['num2'] = 0
                    break
                if event.key == keyConf['imageOpen'] and Conf.imageOpenName:
                    # imageOrderへの追加削除はmainメソッド内で行う
                    self.__status['num2'] = 1
                    self.__rsrc.imageDic[Conf.imageOpenName].xy = Conf.imageOpenXY

                page = self.__status['page']
                maxIndex = len(self.__rsrc.textList) - 1
                if event.key == keyConf['turnPage'] or event.key == K_RETURN:
                    # ページ送りとSoundインスタンスputプロパティの初期化
                    if page == maxIndex:
                        self.resetStatus()
                    else:
                        self.__status['page'] += 1
                    self.__status['num'] = 0
                    self.__rsrc.soundDic[Conf.soundTurnPage].play()
                    self.__rsrc.resetSound()
                if event.key == keyConf['backPage']:
                    # ページ戻りモードへ
                    if self.__status['page'] > 0:
                        self.__status['pageBack'] += 1
                        self.__status['mode'] = self.__status['mode'] + '__back'
                if event.key == keyConf['showHelp']:
                    self.__status['message'] = Conf.helpConf['message']
                    self.__status['mode'] = self.__status['mode'] + '__announce'
                if event.key == keyConf['goToStart']:
                    self.resetStatus()
                if event.key == keyConf['save1']:
                    self.saveData(1)
                if event.key == keyConf['save2']:
                    self.saveData(2)
                if event.key == keyConf['save3']:
                    self.saveData(3)
                if event.key == keyConf['save4']:
                    self.saveData(4)
                if event.key == keyConf['load1']:
                    self.loadData(1)
                if event.key == keyConf['load2']:
                    self.loadData(2)
                if event.key == keyConf['load3']:
                    self.loadData(3)
                if event.key == keyConf['load4']:
                    self.loadData(4)

    def backMode(self):
        """ページ戻りモードのときゲームループに差し込まれるメソッド。"""
        # 現在のページに戻ってきたらモードを戻す
        if self.__status['pageBack'] == 0:
            self.__status['mode'] = self.__status['mode'].rstrip('__back')

        # 「いまページ戻りモードですよ」の通知
        textSize = font.size(Conf.pageBackMode['message'])
        pygame.draw.rect(screen, Conf.pageBackMode['boxColor'],
            Rect(50,50,textSize[0]+20, textSize[1]+20))
        text = font.render(Conf.pageBackMode['message'], True, Conf.pageBackMode['mesColor'])
        screen.blit(text, (60,60))

        # 通常行のみblit
        draft = self.__rsrc.textList[self.__status['page'] - self.__status['pageBack']]
        lineList = draft.split('\n')
        textLineNum = 0
        for line in lineList:
            # 基本的にタグは飛ばすが、指定タグは処理する
            for string in Conf.pageBackMode['pass']:
                if line.startswith(string):
                    self.dialogEvent(line)
            if (line.startswith('<event ') and line.endswith('>')):
                continue
            elif line.startswith('#'):
                continue
            else:
                text = font.render(line, True, Conf.dialogColor)
                screen.blit(text, (Conf.dialogX, Conf.dialogY+font.get_linesize()*textLineNum))
                textLineNum += 1

        for event in pygame.event.get():

            event = self.swicth_mouse_click(event)

            if event.type == QUIT:
                sys.exit()
            if event.type == KEYDOWN:
                if event.key == K_F4 and bool(event.mod and KMOD_ALT):
                    sys.exit()
                # pageBackの範囲は 0~page
                if event.key == keyConf['turnPage'] or event.key == K_RETURN:
                    if self.__status['pageBack'] > 0:
                        self.__status['pageBack'] -= 1
                        self.skipTagLines(False)
                if event.key == keyConf['backPage']:
                    if self.__status['pageBack'] < self.__status['page']:
                        self.__status['pageBack'] += 1
                        self.skipTagLines(True)

    def skipTagLines(self, back):
        """通常行の含まれるパラグラフまでpageBack数をスキップする。
        backがFalseならページを進め、Trueならページを戻す。"""
        draft = self.__rsrc.textList[self.__status['page'] - self.__status['pageBack']]
        lineList = draft.split('\n')
        normalLineExists = False
        for line in lineList:
            for string in Conf.pageBackMode['pass']:
                if line.startswith(string):
                    normalLineExists = True
            # <event name=skip back>のときは通常行があろうとスキップする
            if 'event name=skip' in line and 'back' in line:
                normalLineExists = False
                break
            if (line.startswith('<event ') and line.endswith('>')):
                continue
            elif line.startswith('#'):
                continue
            else:
                normalLineExists = True
        if normalLineExists:
            return
        else:
            # スキップした結果0~pageの範囲を飛び出すようなら元に戻す
            if not back:
                self.__status['pageBack'] -= 1
                if self.__status['pageBack'] < 0:
                    self.__status['pageBack'] += 1
                    self.skipTagLines(True)
                else:
                    self.skipTagLines(back)
            else:
                self.__status['pageBack'] += 1
                if self.__status['pageBack'] > self.__status['page']:
                    self.__status['pageBack'] -= 1
                    self.skipTagLines(False)
                else:
                    self.skipTagLines(back)

    def dialogEvent(self, tag):
        """ダイアログにイベントタグが現れたときの処理。"""
        parser = TagParse()
        parser.feed(tag)
        dic = parser.dic
        if   dic['name'] in 'image':
            self.imageTag(dic)
        elif dic['name'] in 'sound':
            self.soundTag(dic)
        elif dic['name'] in 'bgm':
            self.bgmTag(dic)
        elif dic['name'] in 'text':
            self.textTag(dic)
        elif dic['name'] in 'skip':
            self.skipTag(dic)
        elif dic['name'] in 'dice':
            self.diceTag(dic)

    def imageTag(self, dic):
        """imageタグから入るメソッド。"""
        # property: name file x y put remove changefrom changeto shake
        if 'x' in dic:
            self.__rsrc.imageDic[dic['file']].xy[0] = int(dic['x'])
        if 'y' in dic:
            self.__rsrc.imageDic[dic['file']].xy[1] = int(dic['y'])
        if ('put' in dic) and (dic['file'] not in self.__status['imageOrder']):
            self.__status['imageOrder'].append(dic['file'])
            # imageOrder内にリンク画像同士があったら今追加したのを削除 = リンク画像は片方しか表示できない
            for linkingDic in Conf.linkingList:
                for key,imageDic in linkingDic.items():
                    if (imageDic['main'] in self.__status['imageOrder']
                            and imageDic['back'] in self.__status['imageOrder']):
                        self.__status['imageOrder'].remove(dic['file'])
        if 'remove' in dic:
            if dic['file'] not in self.__status['imageOrder']:
                # いつでも画像オープンの画像を消そうとしてる場合は、num2が1だったら無視する
                if dic['file'] == Conf.imageOpenName and self.__status['num2'] == 1:
                    pass
                # リストにないのにremoveしようとするのはただのミスか、あるいはリンク画像の可能性
                for linkingDic in Conf.linkingList:
                    for key,imageDic in linkingDic.items():
                        if (dic['file'] == imageDic['main']
                                and imageDic['back'] in self.__status['imageOrder']):
                            self.__status['imageOrder'].remove(imageDic['back'])
                        elif (dic['file'] == imageDic['back']
                                and imageDic['main'] in self.__status['imageOrder']):
                            self.__status['imageOrder'].remove(imageDic['main'])
                        else:
                            # ミスなら
                            pass
            else:
                self.__status['imageOrder'].remove(dic['file'])
        if 'removeall' in dic:
            self.__status['imageOrder'] = []
        if ('changefrom' in dic and 'changeto' in dic
                    and dic['changefrom'] in self.__status['imageOrder']):
            targetIndex = self.__status['imageOrder'].index(dic['changefrom'])
            self.__status['imageOrder'][targetIndex] = dic['changeto']
        if 'shake' in dic:
            # 指定の画像の座標をフレーム加算ごとに動かす <event name=image file="%s" x=%s y=%s shake=5 put>
            # 左下、右上、下、左上、右、左、右下、上をそれぞれフレーム数/6の余りと対応させる
            baseX = self.__rsrc.imageDic[dic['file']].xy[0]
            baseY = self.__rsrc.imageDic[dic['file']].xy[1]
            shake = int(dic['shake'])
            lisNum = self.__status['frameNum'] % 16
            if   lisNum in {0,1}:
                xy = [baseX-shake, baseY+shake]
            elif lisNum in {2,3}:
                xy = [baseX+shake, baseY-shake]
            elif lisNum in {4,5}:
                xy = [baseX, baseY+shake]
            elif lisNum in {6,7}:
                xy = [baseX-shake, baseY-shake]
            elif lisNum in {8,9}:
                xy = [baseX+shake, baseY]
            elif lisNum in {10,11}:
                xy = [baseX-shake, baseY]
            elif lisNum in {12,13}:
                xy = [baseX+shake, baseY-shake]
            elif lisNum in {14,15}:
                xy = [baseX, baseY-shake]
            self.__rsrc.imageDic[dic['file']].xy[0] = xy[0]
            self.__rsrc.imageDic[dic['file']].xy[1] = xy[1]

    def soundTag(self, dic):
        """soundタグから入るメソッド。"""
        # property: file volume play
        if 'volume' in dic:
            self.__rsrc.soundDic[dic['file']].volume(float(dic['volume']))
        if 'play' in dic and self.__rsrc.soundDic[dic['file']].put == False:
            self.__rsrc.soundDic[dic['file']].play()
        if 'reset' in dic:
            self.__rsrc.soundDic[dic['file']].put = False

    def bgmTag(self, dic):
        """bgmタグから入るメソッド。"""
        # property: file volume play stop
        if 'file' in dic and dic['file'] != self.__rsrc.bgm.name:
            self.__rsrc.bgm.stop()
            self.__rsrc.bgm.change(dic['file'])
        if 'volume' in dic:
            self.__rsrc.bgm.volume(float(dic['volume']))
        if self.__rsrc.bgm.put == False:
            if 'play' in dic:
                self.__rsrc.bgm.play()
        else:
            if 'stop' in dic:
                self.__rsrc.bgm.stop()

    def textTag(self, dic):
        """textタグから入るメソッド。"""
        # property: string color fontsize x y
        string = ' ' if not 'string' in dic else dic['string']
        color = (255,255,255) if not 'color' in dic else tuple(dic['color'])
        font = Conf.dialogFont if not 'font' in dic else dic['font']
        fontsize = 18 if not 'fontsize' in dic else int(dic['fontsize'])
        x = 0 if not 'x' in dic else int(dic['x'])
        y = 0 if not 'y' in dic else int(dic['y'])
        font = pygame.font.Font(Conf.cassette+os.sep+'other'+os.sep+font, fontsize)
        text = font.render(string, True, color)
        screen.blit(text, (x, y))

    def skipTag(self, dic):
        """skipタグから入るメソッド。"""
        # property: pause back
        page = self.__status['page']
        # この処理は現在がdialogModeのときにだけ必要
        if self.__status['mode'] == 'dialog':
            maxIndex = len(self.__rsrc.textList) - 1
            self.__status['page'] = page+1 if page != maxIndex else maxIndex
        else:
            self.__status['page'] += 1
        self.__rsrc.resetSound()
        if 'pause' in dic:
            pygame.time.delay(int(dic['pause']))
        if 'back' in dic:
            # これはページ戻りモードのときのみ作用
            pass

    def diceTag(self, dic):
        """diceタグから入るメソッド。"""
        # property: skill result x y
        passingMark = ''
        succeed = ''
        if self.__status['num'] != Conf.diceNum:
            result = random.randint(1, 100)
            if dic['skill'] in Conf.diceDic:
                passingMark = Conf.diceDic[dic['skill']]
            self.__status['num'] += 1
        else:
            result = dic['result']
            if dic['skill'] in Conf.diceDic:
                # Configで技能登録されてるスキルだったら技能値(passingMark)と成功失敗(succeed)を表示する
                passingMark = Conf.diceDic[dic['skill']]
                if int(dic['result']) > passingMark:
                    succeed = '→ 失敗…'
                    if int(dic['result']) >= 96:
                        succeed = '→ ﾌｧﾝﾌﾞﾙ……'
                else:
                    succeed = '→ 成功!'
                    if int(dic['result']) <= 5:
                        succeed = '→ ｸﾘﾃｨｶﾙ!!'
        string1 = '%s: %s' % (dic['skill'], passingMark)
        string2 = '%s %s' % (result, succeed)
        text1 = font.render(string1, True, Conf.dialogColor)
        text2 = font.render(string2, True, Conf.dialogColor)
        screen.blit(text1, (int(dic['x']), int(dic['y'])))
        screen.blit(text2, (int(dic['x']), int(dic['y'])+font.get_linesize()))

    def resetStatus(self):
        """__statusをデフォルト値へ戻す(オープニング画面へ戻す)。"""
        for key,value in self.__status['default'].items():
            self.__status[key] = value

    def saveData(self, savenum):
        """現在のrsrcとstatusを保存する。"""
        jsonRsrc = self.__rsrc.exportJson()
        jsonStatus = json.dumps(self.__status)
        # そのsavenumのレコードなかったら先に作る
        DBAccess.igsertData({'savenum':savenum}, {})
        # セーブする
        data = {
            'rsrc':jsonRsrc,
            'status':jsonStatus,
            'paragraph':len(self.__rsrc.textList),
        }
        DBAccess.updateData(data, {'savenum':savenum})
        # セーブしたことを言う
        self.__status['message'] = '%s番にセーブしました!' % savenum
        self.__status['mode'] = self.__status['mode'] + '__announce'

    def loadData(self, savenum):
        """DBからもってきたrsrcとstatusを反映する。"""
        rows = DBAccess.selectData({'savenum':savenum})
        if rows == []:
            # セーブがなければそう言う
            self.__status['message'] = '%s番にセーブデータはありません!' % savenum
            self.__status['mode'] = self.__status['mode'] + '__announce'
            return
        data = rows[0]
        self.__rsrc.importJson(data['rsrc'])
        self.__status = json.loads(data['status'])
        # ロード完了を言う
        self.__status['message'] = '%s番のデータをロードしました!' % savenum
        self.__status['mode'] = self.__status['mode'] + '__announce'

    def swicth_mouse_click(self, event):
        '''macに対応するためのマウスクリック変換。'''

        return accept_mouse_click.switch(
            event,
            left_click  = keyConf['turnPage'],
            scroll_click= keyConf['imageOpen'],
            right_click = keyConf['backPage'],
            scroll_up   = keyConf['showHelp'],
            scroll_down = K_DOWN
            )


class DBAccess:
    """DBとの仲介をするメソッドはこちらのクラスに。"""

    dbPath = Conf.cassette+os.sep+'other'+os.sep+'save.sqlite3'

    dbFields = [
        'id',
        'savenum',
        'rsrc',
        'status',
        'paragraph',
    ]

    def assoc(trash):
        """い つ も の。"""
        rows = []
        for i in range(len(trash)):
            rows.append({})
            for j in range(len(trash[i])):
                rows[i][DBAccess.dbFields[j]] = trash[i][j]
        return rows

    def selectData(condDic={}):
        """WHERE条件をディクショナリで受け取り、selectしてリストで返す。"""
        connection = sqlite3.connect(DBAccess.dbPath)
        cursor = connection.cursor()
        sql = 'SELECT * FROM saves WHERE 1=1 '
        for key,value in condDic.items():
            # メンドいのでプリペアドステートメントは使わない。
            sql += 'AND %s=%s ' % (key, value)
        cursor.execute(sql)
        trash = cursor.fetchall()
        if trash:
            rows = DBAccess.assoc(trash)
        else:
            rows = []
        cursor.close()
        connection.close()
        return rows

    def igsertData(valueDic={}, condDic={}):
        """そのsavenumがなければinsertする。"""
        connection = sqlite3.connect(DBAccess.dbPath)
        cursor = connection.cursor()
        fields = ''
        values = ''
        for key,value in valueDic.items():
            # メンドいのでプリペアドステートメントは使わない。
            fields += key + ','
            values += str(value) + ','
        fields = fields.rstrip(',')
        values = values.rstrip(',')
        sql = 'INSERT OR IGNORE INTO saves (%s) VALUES (%s)' % (fields, values)
        for key,value in condDic.items():
            sql += 'AND %s=%s ' % (key, value)
        cursor.execute(sql)
        connection.commit()
        cursor.close()
        connection.close()

    def updateData(valueDic={}, condDic={}):
        """valueDicの内容をcondDicの条件でupdateする。"""
        connection = sqlite3.connect(DBAccess.dbPath)
        cursor = connection.cursor()
        stmt = ''
        bind = []
        for key,value in valueDic.items():
            # json入るのでプリペアドステートメント使う(文字列の直書きちょっとあやふや)。
            stmt += '%s = ?,' % key
            bind.append(value)
        stmt = stmt.rstrip(',')
        sql = 'UPDATE saves SET %s WHERE 1=1 ' % stmt
        for key,value in condDic.items():
            # メンドいのでプリペアドステートメントは使わない。
            sql += 'AND %s=%s ' % (key, value)
        cursor.execute(sql, tuple(bind))
        connection.commit()
        cursor.close()
        connection.close()


class FrameError:
    """エラーログを生成するクラス。"""

    def __init__(self, e):
        """エラーをログに残す。"""
        now = datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')
        with open(Conf.cassette+os.sep+'log'+os.sep+'error.txt', 'a', encoding='utf-8') as f:
            text = '\nError happened %s\n%s' % (now, e)
            f.write(text)
        print('エラーが発生したんで終了します。詳細はエラーログ(log/error.txt)をご覧あれ。')
        print('ログみてもワケワカメだったら開発者にerror.txtを送ってね。')
        sys.exit()


if __name__ == '__main__':
    pygame.init()
    screenSize = (640, 480)
    screen = pygame.display.set_mode(screenSize)
    framerate = Conf.framerate
    clock = pygame.time.Clock()
    icon = Images(Conf.cassette+os.sep+'other'+os.sep+Conf.dialogIcon, (0,0))
    pygame.display.set_icon(icon.surface)
    pygame.display.set_caption(Conf.dialogTitle)
    font = pygame.font.Font(Conf.cassette+os.sep+'other'+os.sep+Conf.dialogFont, Conf.dialogFontSize)
    keyDic = {
        'z': K_z,
        'x': K_x,
        'c': K_c,
        '1': K_1,
        '2': K_2,
        '3': K_3,
        '4': K_4,
        '5': K_5,
        '6': K_6,
        '7': K_7,
        '8': K_8,
        'f1': K_F1,
        'f2': K_F2,
        'f3': K_F3,
        'f4': K_F4,
        'f5': K_F5,
        'f6': K_F6,
        'f7': K_F7,
        'f8': K_F8,
        'f11': K_F11,
        'f12': K_F12,
    }
    keyConf = {
        'turnPage': keyDic[Conf.keyConf['turnPage']],
        'backPage': keyDic[Conf.keyConf['backPage']],
        'imageOpen': keyDic[Conf.keyConf['imageOpen']],
        'save1': keyDic[Conf.keyConf['save1']],
        'save2': keyDic[Conf.keyConf['save2']],
        'save3': keyDic[Conf.keyConf['save3']],
        'save4': keyDic[Conf.keyConf['save4']],
        'load1': keyDic[Conf.keyConf['load1']],
        'load2': keyDic[Conf.keyConf['load2']],
        'load3': keyDic[Conf.keyConf['load3']],
        'load4': keyDic[Conf.keyConf['load4']],
        'showHelp': keyDic[Conf.keyConf['showHelp']],
        'goToStart': keyDic[Conf.keyConf['goToStart']],
    }

    # frame = DialogFrame()
    # frame.main()

    try:
        frame = DialogFrame()
        frame.main()
    except Exception as e:
        FrameError(traceback.format_exc())
