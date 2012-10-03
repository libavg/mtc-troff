#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# TROff - A Multitouch TRON Clone
#
# Copyright (C) 2011 Thomas Schott, <scotty at c-base dot org>
#
# TROff is free software: You can redistribute it and/or
# modify it under the terms of the GNU General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# TROff is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with TROff. If not, see <http://www.gnu.org/licenses/>.

from libavg import avg, gameapp, Point2D
from libavg.utils import getMediaDir
from math import floor, ceil, pi
from random import choice, randint
from cPickle import load


BASE_GRIDSIZE = Point2D(320, 180)
BASE_BORDERWIDTH = 10
IDLE_TIMEOUT = 10000
PLAYER_COLORS = ['00FF00', 'FF00FF', '00FFFF', 'FFFF00']

g_player = avg.Player.get()
g_gridSize = 4


#def logMsg(msg):
#    print '[%s] %s' %(g_player.getFrameTime(), msg)


class Button(object):
    def __init__(self, parent, color, icon, callback):
        w, h = parent.size
        if icon == '^': # 'clear player wins' button
            self.__node = avg.PolygonNode(pos=[(w, h), (0, h), (0, 0)])
        elif icon == '<': # 'turn left' button
            self.__node = avg.PolygonNode(pos=[(g_gridSize, 0), (w, 0), (w, h - g_gridSize)])
        elif icon == '>': # 'turn right' button
            self.__node = avg.PolygonNode(pos=[(w - g_gridSize, h), (0, h), (0, g_gridSize)])
        elif icon == '#': # 'clear all player wins' button
            # WinCounter size + some offset
            size = Point2D(g_gridSize * 44, g_gridSize * 44)
            self.__node = avg.RectNode(pos=parent.size / 2 - size, size=size * 2)
        elif icon[0] == 'x': # 'exit' button, icon[1] == 'l'|'r' -> left|right
            scale = g_gridSize * 6
            xOffset = parent.width / 4 * (3 if icon[1] == 'r' else 1)
            yOffset = parent.height / 2
            pos = map(lambda (x, y): (x * scale + xOffset, y * scale + yOffset),
                    [(-2, -1), (-1, -2), (0, -1), (1, -2), (2, -1), (1, 0),
                     (2, 1), (1, 2), (0, 1), (-1, 2), (-2, 1), (-1, 0)])
            self.__node = avg.PolygonNode(pos=pos)
        else:
            if icon == 'O': # 'start' button
                self.__node = avg.CircleNode(pos=parent.size / 2, r=h / 4,
                        strokewidth=2)
            else: # icon == 'o': 'join' button 
                self.__node = avg.CircleNode(pos=parent.size / 2, r=h / 2)
        self.__node.color = color
        self.__node.opacity = 0
        self.__node.sensitive = False
        parent.appendChild(self.__node)

        self.__cursorID = None
        self.__callback = callback
        self.__node.setEventHandler(avg.CURSORDOWN, avg.MOUSE | avg.TOUCH, self.__onDown)
        self.__node.setEventHandler(avg.CURSORUP, avg.MOUSE | avg.TOUCH, self.__onUp)

    def activate(self):
        self.__node.fillopacity = 0.2 # needs libavg-r4503 bugfix to avoid crash
        avg.fadeIn(self.__node, 200, 0.5)
        self.__node.sensitive = True

    def deactivate(self):
        def hideFill():
            self.__node.fillopacity = 0

        if not self.__cursorID is None:
            self.__node.releaseEventCapture(self.__cursorID)
            self.__cursorID = None
        self.__node.sensitive = False
        avg.fadeOut(self.__node, 200, hideFill)

    def __onDown(self, event):
        if not self.__cursorID is None:
            return False
        self.__cursorID = event.cursorid
        self.__node.setEventCapture(self.__cursorID)

        avg.LinearAnim(self.__node, 'fillopacity', 200, 1, 0.2).start() # libavg-r4503
        self.__callback()
        return False # dispatch event further (for idle timer reset)

    def __onUp(self, event):
        if not self.__cursorID == event.cursorid:
            return False
        self.__node.releaseEventCapture(self.__cursorID)
        self.__cursorID = None
        return True # stop event propagation


class Controller(avg.DivNode):
    def __init__(self, player, joinCallback, parent=None, *args, **kwargs):
        kwargs['pivot'] = (0, 0)
        super(Controller, self).__init__(*args, **kwargs)
        self.registerInstance(self, parent)

        self.__player = player
        self.__joinCallback = joinCallback

        self.__joinButton = Button(self, self.__player.color, 'o',
                self.__joinPlayer)
        self.__leftButton = Button(self, self.__player.color, '<',
                lambda: self.__player.changeHeading(1))
        self.__rightButton = Button(self, self.__player.color, '>',
                lambda: self.__player.changeHeading(-1))

        self.__player.registerController(self)

    def preStart(self, clearWins):
        self.__joinButton.activate()
        self.sensitive = True
        self.__playerJoined = False
        if clearWins:
            self.__player.clearWins()

    def start(self):
        if self.__playerJoined:
            self.sensitive = True

    def deactivateUnjoined(self):
        if not self.__playerJoined:
            self.__joinButton.deactivate()
            self.sensitive = False

    def deactivate(self):
        self.__leftButton.deactivate()
        self.__rightButton.deactivate()
        self.sensitive = False

    def __joinPlayer(self):
        self.__joinButton.deactivate()
        self.sensitive = False
        self.__leftButton.activate()
        self.__rightButton.activate()
        self.__joinCallback(self.__player)
        self.__player.setReady()
        self.__playerJoined = True


class WinCounter(avg.DivNode):
    def __init__(self, color, parent=None, *args, **kwargs):
        def triangle(p0, p1, p2):
            avg.PolygonNode(parent=self, pos=[p0, p1, p2], color=color, fillcolor=color)

        kwargs['pos'] = parent.size / 2 + Point2D(g_gridSize, g_gridSize)
        kwargs['pivot'] = (-g_gridSize, -g_gridSize)
        super(WinCounter, self).__init__(*args, **kwargs)
        self.registerInstance(self, parent)

        self.__count = 0

        s1 = kwargs['size'].x
        s12 = s1 / 2
        s14 = s1 / 4
        s34 = s1 * 3 / 4
        triangle((0, 0), (s14, s14), (0, s12))
        triangle((0, s12), (s14, s14), (s12, s12))
        triangle((s12, s12), (s14, s34), (0, s12))
        triangle((0, s12), (s14, s34), (0, s1))
        triangle((0, s1), (s14, s34), (s12, s1))
        triangle((s12, s1), (s14, s34), (s12, s12))
        triangle((s12, s12), (s34, s34), (s12, s1))
        triangle((s12, s1), (s34, s34), (s1, s1))

        resetButton = Button(self, color, '^', lambda: self.reset(True)).activate()
        self.__clearSound = avg.SoundNode(parent=self, href='clear.wav')

    @property
    def count(self):
        return self.__count

    def inc(self):
        self.getChild(self.__count).fillopacity = 0.5
        self.__count += 1

    def reset(self, playSound=False):
        if playSound:
            self.__clearSound.play()
        for i in range(0, self.__count):
            self.getChild(i).fillopacity = 0
        self.__count = 0


class Player(avg.DivNode):
    def __init__(self, color, startPos, startHeading, parent=None, *args, **kwargs):
        kwargs['opacity'] = 0
        kwargs['sensitive'] = False
        super(Player, self).__init__(*args, **kwargs)
        self.registerInstance(self, parent)

        self._color = color
        self.__startPos = Point2D(startPos)
        self.__startHeading = Point2D(startHeading)
        self._lines = []

        self.__node = avg.DivNode(parent=self, pivot=(0, 0))
        self.__body = avg.CircleNode(parent=self.__node, color=self._color)
        avg.LineNode(parent=self.__node, pos1=(-g_gridSize * 2, 0), pos2=(g_gridSize * 2, 0),
                color=self._color, strokewidth=3)
        avg.LineNode(parent=self.__node, pos1=(0, -g_gridSize * 2), pos2=(0, g_gridSize * 2),
                color=self._color, strokewidth=3)

        self.__nodeAnim = avg.ContinuousAnim(self.__node, 'angle', 0, 3.14)
        self.__explodeAnim = avg.ParallelAnim(
                (avg.LinearAnim(self.__body, 'r', 200, self.__body.r, g_gridSize * 6),
                 avg.LinearAnim(self.__body, 'opacity', 200, 1, 0)),
                None, self.__remove)

    @property
    def _pos(self):
        return self.__node.pos

    def _setReady(self):
        self.__node.pos = self.__startPos
        self.__heading = Point2D(self.__startHeading)
        self.__body.r = g_gridSize
        self.__body.strokewidth = 1
        self.__body.opacity = 1
        self.__nodeAnim.start()
        avg.fadeIn(self, 200)
        self.__createLine()

    def _setDead(self, explode):
        self.__nodeAnim.abort()
        if explode:
            self.__body.strokewidth = 3
            self.__explodeAnim.start()
        else:
            self.__remove()

    def _step(self):
        self.__node.pos += self.__heading
        # lines always run rightwards or downwards (for easier collision checking)
        if self.__heading.x < 0 or self.__heading.y < 0:
            self._lines[0].pos1 = self.__node.pos
        else:
            self._lines[0].pos2 = self.__node.pos

    def _changeHeading(self, heading):
        if self.__heading.x == 0:
            self.__heading.x = heading * self.__heading.y
            self.__heading.y = 0
        else:
            self.__heading.y = -heading * self.__heading.x
            self.__heading.x = 0
        self.__createLine()

    def __createLine(self):
        self._lines.insert(0, avg.LineNode(parent=self,
                pos1=self.__node.pos, pos2=self.__node.pos,
                color=self._color, strokewidth=2))

    def __remove(self):
        def removeLines():
            for l in self._lines:
                l.unlink()
            self._lines = []

        avg.fadeOut(self, 200, removeLines)


class RealPlayer(Player):
    def __init__(self, color, startPos, startHeading, winsDiv, winsSize, winsAngle,
                *args, **kwargs):
        kwargs['size'] = kwargs['parent'].size
        super(RealPlayer, self).__init__(color, startPos, startHeading, *args, **kwargs)

        self.__wins = WinCounter(self._color,
                size=winsSize, parent=winsDiv, angle=winsAngle)
        self.incWins = self.__wins.inc
        self.clearWins = self.__wins.reset

        self.__joinSound = avg.SoundNode(parent=self, href='join.wav')
        self.__crashSound = avg.SoundNode(parent=self, href='crash.wav')
        self.__shieldSound = avg.SoundNode(parent=self, href='shield.wav')
        self.__crossSound = avg.SoundNode(parent=self, href='cross.wav')

    @property
    def color(self):
        return self._color

    @property
    def lines(self):
        return self._lines

    @property
    def wins(self):
        return self.__wins.count

    def registerController(self, controller):
        self.__controller = controller

    def setReady(self):
        self.__joinSound.play()
        super(RealPlayer, self)._setReady()
        self.__shield = None

    def setDead(self, explode=True):
        if explode:
            self.__crashSound.play()
        super(RealPlayer, self)._setDead(explode)
        if not self.__shield is None:
            self.__shield.jump()
        self.__controller.deactivate()

    def step(self):
        super(RealPlayer, self)._step()
        if not self.__shield is None:
            self.__shield.move(self._pos)

    def changeHeading(self, heading):
        super(RealPlayer, self)._changeHeading(heading)

    def checkCrash(self, players, blocker):
        pos = self._pos
        # check border
        if pos.x == 0 or pos.y == 0 or pos.x == self.width or pos.y == self.height:
            return True
        # check blocker
        if blocker.checkCollision(pos):
            return True
        # check lines
        for p in players:
            if p is self:
                firstLine = 1 # don't check own current line
            else:
                firstLine = 0
            for l in p.lines[firstLine:]:
                if pos.x == l.pos1.x \
                        and l.pos1.y <= pos.y and pos.y <= l.pos2.y \
                        or pos.y == l.pos1.y \
                        and l.pos1.x <= pos.x and pos.x <= l.pos2.x:
                    if self.__shield is None:
                        return True
                    self.__crossSound.play()
                    self.__shield.jump()
                    self.__shield = None
        return False

    def checkShield(self, shield):
        if shield.checkCollision(self._pos):
            self.__shieldSound.play()
            self.__shield = shield
            self.__shield.grab()


class IdlePlayer(Player):
    def __init__(self, demoData, *args, **kwargs):
        color = PLAYER_COLORS[demoData['colorIdx']]
        startPos = Point2D(demoData['startPos']) * g_gridSize
        super(IdlePlayer, self).__init__(color, startPos, (0, -g_gridSize),
                *args, **kwargs)

        self.__route = demoData['route']

    def setReady(self):
        super(IdlePlayer, self)._setReady()
        self.__isRunning = True
        self.__routeIter = iter(self.__route)
        self.__currentPath = self.__routeIter.next()
        self.__stepCounter = self.__currentPath[0] + 1
        self.__respawnTimoutID = None

    def setDead(self, restart=False):
        if self.__isRunning:
            super(IdlePlayer, self)._setDead(restart)
            self.__isRunning = False
        elif not self.__respawnTimoutID is None:
            g_player.clearInterval(self.__respawnTimoutID)
        if restart:
            self.__respawnTimoutID = g_player.setTimeout(randint(600, 1200), self.setReady)

    def step(self):
        if not self.__isRunning:
            return
        self.__stepCounter -= 1
        if self.__stepCounter == 0:
            if not self.__currentPath[1] == 0:
                super(IdlePlayer, self)._changeHeading(self.__currentPath[1])
                self.__currentPath = self.__routeIter.next()
                self.__stepCounter = self.__currentPath[0]
            else:
                self.setDead(True)
                return
        super(IdlePlayer, self)._step()


class AboutPlayer(avg.DivNode):
    def __init__(self, aboutData, parent=None, *args, **kwargs):
        kwargs['sensitive'] = False
        super(AboutPlayer, self).__init__(*args, **kwargs)
        self.registerInstance(self, parent)

        color = PLAYER_COLORS[aboutData['colorIdx']]
        scale = aboutData['size'] * g_gridSize

        self.__textNode = avg.WordsNode(parent=self, text=aboutData['text'], color=color,
                font='Ubuntu', fontsize=scale, alignment='center', opacity=0)
        self.size = self.__textNode.size + Point2D(4, 1) * g_gridSize
        self.size = (ceil(self.width / g_gridSize) * g_gridSize,
                ceil(self.height / g_gridSize) * g_gridSize)
        self.__textNode.pos = (0, (self.height - self.__textNode.height) / 2)

        aboutData['startPos'] = Point2D(-self.width / 2, self.height) / g_gridSize
        aboutData['route'] = [
                (int(self.height / g_gridSize), -1),
                (int(self.width / g_gridSize), -1),
                (int(self.height / g_gridSize), -1),
                (int(self.width / g_gridSize), 0)]
        self.__idlePlayer = IdlePlayer(aboutData, parent=self)

    def setReady(self):
        avg.fadeIn(self.__textNode, 200)
        self.__idlePlayer.setReady()

    def setDead(self, restart=False):
        self.__idlePlayer.setDead()
        avg.fadeOut(self.__textNode, 200)

    def step(self):
        self.__idlePlayer.step()


class DragItem(avg.DivNode):
    def __init__(self, iconNode, parent=None, *args, **kwargs):
        self._posOffset = Point2D(g_gridSize * 8, g_gridSize * 8)
        w, h = parent.size
        kwargs['size'] = self._posOffset * 2
        super(DragItem, self).__init__(*args, **kwargs)
        self.registerInstance(self, parent)

        self.__minPosX = int(-self._posOffset.x) + g_gridSize
        self.__maxPosX = int(w - self._posOffset.x)
        self.__posX = range(self.__minPosX, self.__maxPosX, g_gridSize)
        self.__minPosY = int(-self._posOffset.y) + g_gridSize
        self.__maxPosY = int(h - self._posOffset.y)
        self.__posY = range(self.__minPosY, self.__maxPosY, g_gridSize)

        self.__node = iconNode
        self.__node.opacity = 0
        self.appendChild(self.__node)

        self.__cursorID = None
        self.setEventHandler(avg.CURSORDOWN, avg.MOUSE | avg.TOUCH, self._onDown)
        self.setEventHandler(avg.CURSORUP, avg.MOUSE | avg.TOUCH, self.__onUp)
        self.setEventHandler(avg.CURSORMOTION, avg.MOUSE | avg.TOUCH, self.__onMotion)

    def activate(self):
        self.__active = True
        self.__flash()

    def deactivate(self):
        self.__active = False

    def jump(self):
        self.pos = (choice(self.__posX), choice(self.__posY))

    def checkCollision(self, pos):
        if not self.__cursorID is None:
            return False # no collision when dragging
        dist = self.pos + self._posOffset - pos
        if abs(dist.x) <= g_gridSize and abs(dist.y) <= g_gridSize:
            return True
        return False

    def __flash(self):
        if self.__active:
            avg.LinearAnim(self.__node, 'opacity', 600, 1, 0).start()
            avg.LinearAnim(self.__node, 'fillopacity', 600, 1, 0, False,
                    None, self.__flash).start()

    def _onDown(self, event):
        if not self.__cursorID is None:
            return False
        self.__cursorID = event.cursorid
        self.setEventCapture(self.__cursorID)
        self.__dragOffset = event.pos - self.pos
        return True

    def __onUp(self, event):
        if not self.__cursorID == event.cursorid:
            return False
        self.releaseEventCapture(self.__cursorID)
        self.__cursorID = None
        return True

    def __onMotion(self, event):
        if not self.__cursorID == event.cursorid:
            return False
        pos = (event.pos - self.__dragOffset) / g_gridSize
        pos = Point2D(round(pos.x), round(pos.y)) * g_gridSize
        if self.__minPosX <= pos.x and pos.x < self.__maxPosX \
                and self.__minPosY <= pos.y and pos.y < self.__maxPosY:
            self.pos = pos
        return True


class Shield(DragItem):
    def __init__(self, *args, **kwargs):
        icon = avg.CircleNode(r=g_gridSize * 2)
        super(Shield, self).__init__(icon, *args, **kwargs)

        icon.pos = self._posOffset

    def jump(self):
        super(Shield, self).jump()
        self.__isGrabbed = False

    def move(self, pos):
        self.pos = pos - self._posOffset

    def checkCollision(self, pos):
        if self.__isGrabbed:
            return False
        return super(Shield, self).checkCollision(pos)

    def grab(self):
        self.__isGrabbed = True

    def _onDown(self, event):
        if self.__isGrabbed:
            return False
        return super(Shield, self)._onDown(event)


class Blocker(DragItem):
    def __init__(self, *args, **kwargs):
        icon = avg.RectNode(size=(g_gridSize * 3, g_gridSize * 3),
                color='FF0000', fillcolor='FF0000')
        super(Blocker, self).__init__(icon, *args, **kwargs)

        icon.pos = self._posOffset - icon.size / 2


class BgAnim(avg.DivNode):
    def __init__(self, parent=None, *args, **kwargs):
        size = parent.size
        self.__maxX, self.__maxY = size
        kwargs['pos'] = (int(size.x / 2), int(size.y / 2))
        kwargs['opacity'] = 0.2
        super(BgAnim, self).__init__(*args, **kwargs)
        self.registerInstance(self, parent)

        avg.LineNode(parent=self, pos1=(-self.__maxX, 0), pos2=(self.__maxX, 0))
        avg.LineNode(parent=self, pos1=(0, -self.__maxY), pos2=(0, self.__maxY))

        self.__heading = Point2D(randint(-1, 1), 0)
        if self.__heading.x == 0:
            self.__heading.y = choice([-1, 1])
        self.__headingCountdown = randint(60, 120)
        self.__onFrameHandlerID = None

    def start(self):
        assert self.__onFrameHandlerID is None
        self.__onFrameHandlerID = g_player.setOnFrameHandler(self.__onFrame)

    def stop(self):
        assert self.__onFrameHandlerID is not None
        g_player.clearInterval(self.__onFrameHandlerID)
        self.__onFrameHandlerID = None

    def __onFrame(self):
        if self.__headingCountdown == 0:
            self.__headingCountdown = randint(60, 120)
            if self.__heading.x == 0:
                self.__heading.x = choice([-1, 1])
                self.__heading.y = 0
            else:
                self.__heading.x = 0
                self.__heading.y = choice([-1, 1])
        else:
            self.__headingCountdown -= 1

        self.pos += self.__heading
        if self.pos.x == 0 or self.pos.x == self.__maxX \
                or self.pos.y == 0 or self.pos.y == self.__maxY:
            self.__heading *= -1
            self.pos += self.__heading


class TROff(gameapp.GameApp):
    def init(self):
        global g_gridSize
        screenSize = g_player.getRootNode().size
        g_gridSize = int(min(floor(screenSize.x / BASE_GRIDSIZE.x),
                floor(screenSize.y / BASE_GRIDSIZE.y)))
        borderWidth = g_gridSize * BASE_BORDERWIDTH
        battlegroundSize = Point2D(
                floor((screenSize.x - borderWidth * 2) / g_gridSize) * g_gridSize,
                floor((screenSize.y - borderWidth * 2) / g_gridSize) * g_gridSize)
        borderWidth = (screenSize - battlegroundSize) / 2.0

        avg.RectNode(parent=self._parentNode, size=screenSize,
                opacity=0, fillcolor='B00000', fillopacity=1)
        avg.RectNode(parent=self._parentNode,
                pos=borderWidth, size=battlegroundSize,
                opacity=0, fillcolor='000000', fillopacity=1)

        battleground = avg.DivNode(parent=self._parentNode,
                pos=borderWidth, size=battlegroundSize, crop=True)

        self.__bgAnims = []
        for i in xrange(4):
            self.__bgAnims.append(BgAnim(parent=battleground))
        self.__initIdleDemo(battleground)

        self.__gameDiv = avg.DivNode(parent=battleground, size=battlegroundSize)
        self.__ctrlDiv = avg.DivNode(parent=self.__gameDiv, size=battlegroundSize)
        self.__winsDiv = avg.DivNode(parent=self.__ctrlDiv, size=battlegroundSize,
                opacity=0, sensitive=False)

        self.__shield = Shield(parent=self.__ctrlDiv)
        self.__blocker = Blocker(parent=self.__ctrlDiv)

        ctrlSize = Point2D(g_gridSize * 42, g_gridSize * 42)
        playerPos = ctrlSize.x + g_gridSize * 2
        self.__controllers = []
        # 1st
        p = RealPlayer(PLAYER_COLORS[0],
                (playerPos, playerPos), (g_gridSize, 0),
                self.__winsDiv, ctrlSize, pi, parent=self.__gameDiv)
        self.__controllers.append(Controller(p, self.joinPlayer,
                parent=self.__ctrlDiv, pos=(g_gridSize, g_gridSize), size=ctrlSize,
                angle=0))
        # 2nd
        p = RealPlayer(PLAYER_COLORS[1],
                (self.__ctrlDiv.size.x - playerPos, playerPos), (-g_gridSize, 0),
                self.__winsDiv, ctrlSize, -pi / 2, parent=self.__gameDiv)
        self.__controllers.append(Controller(p, self.joinPlayer,
                parent=self.__ctrlDiv, pos=(self.__ctrlDiv.size.x - g_gridSize, g_gridSize),
                size=ctrlSize, angle=pi / 2))
        # 3rd
        p = RealPlayer(PLAYER_COLORS[2],
                (playerPos, self.__ctrlDiv.size.y - playerPos), (g_gridSize, 0),
                self.__winsDiv, ctrlSize, pi / 2, parent=self.__gameDiv)
        self.__controllers.append(Controller(p, self.joinPlayer,
                parent=self.__ctrlDiv, pos=(g_gridSize, self.__ctrlDiv.size.y - g_gridSize),
                size=ctrlSize, angle=-pi / 2))
        # 4th
        p = RealPlayer(PLAYER_COLORS[3],
                (self.__ctrlDiv.size.x - playerPos, self.__ctrlDiv.size.y - playerPos),
                (-g_gridSize, 0), self.__winsDiv, ctrlSize, 0, parent=self.__gameDiv)
        self.__controllers.append(Controller(p, self.joinPlayer,
                parent=self.__ctrlDiv,
                pos=(self.__ctrlDiv.size.x - g_gridSize, self.__ctrlDiv.size.y - g_gridSize),
                size=ctrlSize, angle=pi))

        self.__startButton = Button(self.__ctrlDiv, 'FF0000', 'O', self.__start)
        self.__clearButton = Button(self.__ctrlDiv, 'FF0000', '#', self.__clearWins)
        self.__countdownNode = avg.CircleNode(parent=self.__ctrlDiv,
                pos=self.__ctrlDiv.size / 2, r=self.__ctrlDiv.size.y / 4,
                opacity=0, sensitive=False)

        exitCallback = self.quit
        Button(self.__winsDiv, 'FF0000', 'xl', exitCallback).activate()
        Button(self.__winsDiv, 'FF0000', 'xr', exitCallback).activate()

        self.__redSound = avg.SoundNode(parent=battleground, href='red.wav')
        self.__yellowSound = avg.SoundNode(parent=battleground, href='yellow.wav')
        self.__greenSound = avg.SoundNode(parent=battleground, href='green.wav')
        self.__startSound = avg.SoundNode(parent=battleground, href='start.wav')

        self.__preStart()

    def joinPlayer(self, player):
        self.__activePlayers.append(player)
        if len(self.__activePlayers) == 1:
            avg.fadeOut(self.__winsDiv, 200)
            self.__winsDiv.sensitive = False
        elif len(self.__activePlayers) == 2:
            self.__startButton.activate()

    def _getPackagePath(self):
        return __file__

    def _enter(self):
        self.__startSound.play()
        self.__ctrlDiv.sensitive = True
        for bga in self.__bgAnims:
            bga.start()
        self.__startIdleDemo()

    def _leave(self):
        self.__ctrlDiv.sensitive = False
        for bga in self.__bgAnims:
            bga.stop()
        self.__deactivateIdleTimer()

    def __preStart(self, clearWins=False):
        self.__activePlayers = []
        for c in self.__controllers:
            c.preStart(clearWins)
        self.__shield.jump()
        self.__blocker.jump()

    def __start(self):
        def goGreen():
            self.__greenSound.play()
            self.__countdownNode.fillcolor = '00FF00'
            avg.LinearAnim(self.__countdownNode, 'fillopacity', 1000, 1, 0).start()
            for c in self.__controllers:
                c.start()
            self.__onFrameHandlerID = g_player.setOnFrameHandler(self.__onGameFrame)
        def goYellow():
            self.__yellowSound.play()
            self.__countdownNode.fillcolor = 'FFFF00'
            avg.LinearAnim(self.__countdownNode, 'fillopacity', 1000, 1, 0, False,
                    None, goGreen).start()
            self.__shield.activate()
            self.__blocker.activate()
        def goRed():
            self.__redSound.play()
            self.__countdownNode.fillcolor = 'FF0000'
            avg.LinearAnim(self.__countdownNode, 'fillopacity', 1000, 1, 0, False,
                    None, goYellow).start()

        self.__deactivateIdleTimer()
        self.__startButton.deactivate()
        for c in self.__controllers:
            c.deactivateUnjoined()
        goRed()

    def __stop(self, forceClearWins=False):
        def restart():
            for p in self.__activePlayers:
                p.setDead(False)
            avg.fadeIn(self.__winsDiv, 200)
            self.__winsDiv.sensitive = True
            self.__activateIdleTimer()
            if forceClearWins:
                self.__clearButton.activate()
            else:
                self.__preStart()

        g_player.clearInterval(self.__onFrameHandlerID)
        self.__shield.deactivate()
        self.__blocker.deactivate()
        g_player.setTimeout(2000, restart)

    def __clearWins(self):
        self.__startSound.play()
        self.__clearButton.deactivate()
        self.__preStart(True)

    def __onGameFrame(self):
        for p in self.__activePlayers:
            p.step()

        crashedPlayers = []
        for p in self.__activePlayers:
            if p.checkCrash(self.__activePlayers, self.__blocker):
                crashedPlayers.append(p)
        for p in crashedPlayers:
            p.setDead()
            self.__activePlayers.remove(p)

        if len(self.__activePlayers) == 0:
            self.__stop()
        elif len(self.__activePlayers) == 1:
            self.__activePlayers[0].incWins()
            if self.__activePlayers[0].wins == 8:
                self.__stop(True)
            else:
                self.__stop()
        else:
            for p in self.__activePlayers:
                p.checkShield(self.__shield)

    def __initIdleDemo(self, parent):
        self.__idleTimeoutID = None
        self.__idlePlayers = []

        fp = open(getMediaDir(__file__, 'data/idledemo.pickle'), 'r')
        demoData = load(fp)
        fp.close()
        demoDiv = avg.DivNode(parent=parent,
                pos=parent.size / 2 - Point2D(0, g_gridSize * 20))
        for data in demoData:
            self.__idlePlayers.append(IdlePlayer(data, parent=demoDiv))

        fp = open(getMediaDir(__file__, 'data/idleabout.pickle'), 'r')
        aboutData = load(fp)
        fp.close()
        aboutDiv = avg.DivNode(parent=parent,
                pos=parent.size / 2 - Point2D(0, g_gridSize * 10))
        pos = Point2D(0, 0)
        for data in aboutData:
            aboutPlayer = AboutPlayer(data, parent=aboutDiv, pos=pos)
            pos.y += aboutPlayer.height + 4 * g_gridSize
            self.__idlePlayers.append(aboutPlayer)

    def __activateIdleTimer(self):
        assert self.__idleTimeoutID is None
        self.__idleTimeoutID = g_player.setTimeout(IDLE_TIMEOUT, self.__startIdleDemo)
        self.__ctrlDiv.setEventHandler(avg.CURSORDOWN, avg.MOUSE | avg.TOUCH,
                lambda e:self.__restartIdleTimer())

    def __deactivateIdleTimer(self):
        assert self.__idleTimeoutID is not None
        g_player.clearInterval(self.__idleTimeoutID)
        self.__idleTimeoutID = None
        self.__ctrlDiv.setEventHandler(avg.CURSORDOWN, avg.MOUSE | avg.TOUCH, None)

    def __restartIdleTimer(self):
        if not self.__idleTimeoutID is None:
            g_player.clearInterval(self.__idleTimeoutID)
        self.__idleTimeoutID = g_player.setTimeout(IDLE_TIMEOUT, self.__startIdleDemo)

    def __startIdleDemo(self):
        self.__idleTimeoutID = None
        avg.fadeOut(self.__gameDiv, 200)
        self.__ctrlDiv.sensitive = False
        for p in self.__idlePlayers:
            p.setReady()
        self.__gameDiv.setEventHandler(avg.CURSORDOWN, avg.MOUSE | avg.TOUCH,
                lambda e:self.__stopIdleDemo())
        self.__onFrameHandlerID = g_player.setOnFrameHandler(self.__onIdleFrame)

    def __stopIdleDemo(self):
        self.__gameDiv.setEventHandler(avg.CURSORDOWN, avg.MOUSE | avg.TOUCH, None)
        g_player.clearInterval(self.__onFrameHandlerID)
        avg.fadeIn(self.__gameDiv, 200)
        self.__ctrlDiv.sensitive = True
        for p in self.__idlePlayers:
            p.setDead()
        self.__restartIdleTimer()

    def __onIdleFrame(self):
        for p in self.__idlePlayers:
            p.step()


if __name__ == '__main__':
    TROff.start()
