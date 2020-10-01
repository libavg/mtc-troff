#!/usr/bin/env python
# -*- coding: utf-8 -*-

# TROff - A Multitouch TRON Clone
#
# Copyright (C) 2011-2020 Thomas Schott, <scotty at c-base dot org>
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

from libavg import avg, Point2D, player, app, utils
from libavg.utils import getMediaDir
from math import floor, ceil, pi
from random import choice, randint
from cPickle import load


BASE_GRID_SIZE = Point2D(320, 180)
BASE_BORDER_WIDTH = 10
IDLE_TIMEOUT = 10000
PLAYER_COLORS = ['00FF00', 'FF00FF', '00FFFF', 'FFFF00']

g_grid_size = 4


class Button(object):
    def __init__(self, parent, color, icon, callback):
        w, h = parent.size
        if icon == '^':  # 'clear player wins' button
            self.__node = avg.PolygonNode(pos=[(w, h), (0, h), (0, 0)])
        elif icon == '<':  # 'turn left' button
            self.__node = avg.PolygonNode(pos=[(g_grid_size, 0), (w, 0), (w, h - g_grid_size)])
        elif icon == '>':  # 'turn right' button
            self.__node = avg.PolygonNode(pos=[(w - g_grid_size, h), (0, h), (0, g_grid_size)])
        elif icon == '#':  # 'clear all player wins' button
            # WinCounter size + some offset
            size = Point2D(g_grid_size * 44, g_grid_size * 44)
            self.__node = avg.RectNode(pos=parent.size / 2 - size, size=size * 2)
        elif icon[0] == 'x':  # 'exit' button, icon[1] == 'l'|'r' -> left|right
            scale = g_grid_size * 6
            x_offset = parent.width / 4 * (3 if icon[1] == 'r' else 1)
            y_offset = parent.height / 2
            pos = map(
                lambda (x, y): (x * scale + x_offset, y * scale + y_offset), [
                    (-2, -1), (-1, -2), (0, -1), (1, -2), (2, -1), (1, 0),
                    (2, 1), (1, 2), (0, 1), (-1, 2), (-2, 1), (-1, 0)
                ]
            )
            self.__node = avg.PolygonNode(pos=pos)
        else:
            if icon == 'O':  # 'start' button
                self.__node = avg.CircleNode(pos=parent.size / 2, r=h / 4, strokewidth=2)
            else:  # icon == 'o': 'join' button
                self.__node = avg.CircleNode(pos=parent.size / 2, r=h / 2)
        self.__node.color = color
        self.__node.opacity = 0
        self.__node.sensitive = False
        parent.appendChild(self.__node)

        self.__cursor_id = None
        self.__callback = callback
        self.__node.subscribe(avg.Node.CURSOR_DOWN, self.__on_down)
        self.__node.subscribe(avg.Node.CURSOR_UP, self.__on_up)

    def activate(self):
        self.__node.fillopacity = 0.2
        avg.Anim.fadeIn(self.__node, 200, 0.5)
        self.__node.sensitive = True

    def deactivate(self):
        def hide_fill():
            self.__node.fillopacity = 0

        if self.__cursor_id is not None:
            self.__node.releaseEventCapture(self.__cursor_id)
            self.__cursor_id = None
        self.__node.sensitive = False
        avg.Anim.fadeOut(self.__node, 200, hide_fill)

    def __on_down(self, event):
        if self.__cursor_id is not None:
            return
        self.__cursor_id = event.cursorid
        self.__node.setEventCapture(self.__cursor_id)

        avg.LinearAnim(self.__node, 'fillopacity', 200, 1, 0.2).start()
        self.__callback()
        return

    def __on_up(self, event):
        if self.__cursor_id != event.cursorid:
            return
        self.__node.releaseEventCapture(self.__cursor_id)
        self.__cursor_id = None
        return


class Controller(avg.DivNode):
    def __init__(self, player_, join_callback, parent=None, **kwargs):
        kwargs['pivot'] = (0, 0)
        super(Controller, self).__init__(**kwargs)
        self.registerInstance(self, parent)

        self.__player = player_
        self.__join_callback = join_callback

        self.__join_button = Button(self, self.__player.color, 'o', self.__join_player)
        self.__left_button = Button(self, self.__player.color, '<', lambda: self.__player.change_heading(1))
        self.__right_button = Button(self, self.__player.color, '>', lambda: self.__player.change_heading(-1))

        self.__player_joined = False
        self.__player.register_controller(self)

    def pre_start(self, clear_wins):
        self.__join_button.activate()
        self.sensitive = True
        self.__player_joined = False
        if clear_wins:
            self.__player.clear_wins()

    def start(self):
        if self.__player_joined:
            self.sensitive = True

    def deactivate_unjoined(self):
        if not self.__player_joined:
            self.__join_button.deactivate()
            self.sensitive = False

    def deactivate(self):
        self.__left_button.deactivate()
        self.__right_button.deactivate()
        self.sensitive = False

    def __join_player(self):
        self.__join_button.deactivate()
        self.sensitive = False
        self.__left_button.activate()
        self.__right_button.activate()
        self.__join_callback(self.__player)
        self.__player.set_ready()
        self.__player_joined = True


class WinCounter(avg.DivNode):
    def __init__(self, color, parent=None, **kwargs):
        def triangle(p0, p1, p2):
            avg.PolygonNode(parent=self, pos=[p0, p1, p2], color=color, fillcolor=color)

        kwargs['pos'] = parent.size / 2 + Point2D(g_grid_size, g_grid_size)
        kwargs['pivot'] = (-g_grid_size, -g_grid_size)
        super(WinCounter, self).__init__(**kwargs)
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

        self.__reset_button = Button(self, color, '^', lambda: self.reset(True))
        self.__reset_button.activate()
        self.__clear_sound = avg.SoundNode(parent=self, href='clear.wav')

    @property
    def count(self):
        return self.__count

    def inc(self):
        self.getChild(self.__count).fillopacity = 0.5
        self.__count += 1

    def reset(self, play_sound=False):
        if play_sound:
            self.__clear_sound.play()
        for i in range(0, self.__count):
            self.getChild(i).fillopacity = 0
        self.__count = 0


class Player(avg.DivNode):
    def __init__(self, color, start_pos, start_heading, parent=None, **kwargs):
        kwargs['opacity'] = 0
        kwargs['sensitive'] = False
        super(Player, self).__init__(**kwargs)
        self.registerInstance(self, parent)

        self._color = color
        self.__start_pos = Point2D(start_pos)
        self.__start_heading = Point2D(start_heading)
        self._lines = []

        self.__node = avg.DivNode(parent=self, pivot=(0, 0))
        self.__body = avg.CircleNode(parent=self.__node, color=self._color)
        avg.LineNode(
            parent=self.__node, pos1=(-g_grid_size * 2, 0), pos2=(g_grid_size * 2, 0),
            color=self._color, strokewidth=3
        )
        avg.LineNode(
            parent=self.__node, pos1=(0, -g_grid_size * 2), pos2=(0, g_grid_size * 2),
            color=self._color, strokewidth=3
        )

        self.__node_anim = avg.ContinuousAnim(self.__node, 'angle', 0, 3.14)
        self.__explode_anim = avg.ParallelAnim(
            (avg.LinearAnim(self.__body, 'r', 200, self.__body.r, g_grid_size * 6),
             avg.LinearAnim(self.__body, 'opacity', 200, 1, 0)),
            None, self.__remove
        )

    @property
    def _pos(self):
        return self.__node.pos

    def _set_ready(self):
        self.__node.pos = self.__start_pos
        self.__heading = Point2D(self.__start_heading)
        self.__body.r = g_grid_size
        self.__body.strokewidth = 1
        self.__body.opacity = 1
        self.__node_anim.start()
        avg.Anim.fadeIn(self, 200)
        self.__create_line()

    def _set_dead(self, explode):
        self.__node_anim.abort()
        if explode:
            self.__body.strokewidth = 3
            self.__explode_anim.start()
        else:
            self.__remove()

    def _step(self):
        self.__node.pos += self.__heading
        # lines always run rightwards or downwards (for easier collision checking)
        if self.__heading.x < 0 or self.__heading.y < 0:
            self._lines[0].pos1 = self.__node.pos
        else:
            self._lines[0].pos2 = self.__node.pos

    def _change_heading(self, heading):
        if self.__heading.x == 0:
            self.__heading.x = heading * self.__heading.y
            self.__heading.y = 0
        else:
            self.__heading.y = -heading * self.__heading.x
            self.__heading.x = 0
        self.__create_line()

    def __create_line(self):
        self._lines.insert(0, avg.LineNode(
            parent=self, pos1=self.__node.pos, pos2=self.__node.pos,
            color=self._color, strokewidth=2
        ))

    def __remove(self):
        def remove_lines():
            for line in self._lines:
                line.unlink()
            self._lines = []

        avg.Anim.fadeOut(self, 200, remove_lines)


class RealPlayer(Player):
    def __init__(self, color, start_pos, start_heading, wins_div, wins_size, wins_angle, **kwargs):
        kwargs['size'] = kwargs['parent'].size
        super(RealPlayer, self).__init__(color, start_pos, start_heading, **kwargs)

        self.__wins = WinCounter(self._color, size=wins_size, parent=wins_div, angle=wins_angle)
        self.inc_wins = self.__wins.inc
        self.clear_wins = self.__wins.reset

        self.__join_sound = avg.SoundNode(parent=self, href='join.wav')
        self.__crash_sound = avg.SoundNode(parent=self, href='crash.wav')
        self.__shield_sound = avg.SoundNode(parent=self, href='shield.wav')
        self.__cross_sound = avg.SoundNode(parent=self, href='cross.wav')

        self.__controller = None
        self.__shield = None

    @property
    def color(self):
        return self._color

    @property
    def lines(self):
        return self._lines

    @property
    def wins(self):
        return self.__wins.count

    def register_controller(self, controller):
        self.__controller = controller

    def set_ready(self):
        self.__join_sound.play()
        super(RealPlayer, self)._set_ready()
        self.__shield = None

    def set_dead(self, explode=True):
        if explode:
            self.__crash_sound.play()
        super(RealPlayer, self)._set_dead(explode)
        if self.__shield is not None:
            self.__shield.jump()
        self.__controller.deactivate()

    def step(self):
        super(RealPlayer, self)._step()
        if self.__shield is not None:
            self.__shield.move(self._pos)

    def change_heading(self, heading):
        super(RealPlayer, self)._change_heading(heading)

    def check_crash(self, players, blocker):
        pos = self._pos
        # check border
        if pos.x == 0 or pos.y == 0 or pos.x == self.width or pos.y == self.height:
            return True
        # check blocker
        if blocker.check_collision(pos):
            return True
        # check lines
        for player_ in players:
            if player_ is self:
                first_line = 1  # don't check own current line
            else:
                first_line = 0
            for line in player_.lines[first_line:]:
                if (pos.x == line.pos1.x and line.pos1.y <= pos.y <= line.pos2.y) \
                        or (pos.y == line.pos1.y and line.pos1.x <= pos.x <= line.pos2.x):
                    if self.__shield is None:
                        return True
                    self.__cross_sound.play()
                    self.__shield.jump()
                    self.__shield = None
        return False

    def check_shield(self, shield):
        if shield.check_collision(self._pos):
            self.__shield_sound.play()
            self.__shield = shield
            self.__shield.grab()


class IdlePlayer(Player):
    def __init__(self, demo_data, **kwargs):
        color = PLAYER_COLORS[demo_data['colorIdx']]
        start_pos = Point2D(demo_data['startPos']) * g_grid_size
        super(IdlePlayer, self).__init__(color, start_pos, (0, -g_grid_size), **kwargs)

        self.__route = demo_data['route']
        self.__is_running = False
        self.__route_iter = None
        self.__current_path = None
        self.__step_counter = None
        self.__respawn_timeout_id = None

    def set_ready(self):
        super(IdlePlayer, self)._set_ready()
        self.__is_running = True
        self.__route_iter = iter(self.__route)
        self.__current_path = self.__route_iter.next()
        self.__step_counter = self.__current_path[0] + 1
        self.__respawn_timeout_id = None

    def set_dead(self, restart=False):
        if self.__is_running:
            super(IdlePlayer, self)._set_dead(restart)
            self.__is_running = False
        elif self.__respawn_timeout_id is not None:
            player.clearInterval(self.__respawn_timeout_id)
        if restart:
            self.__respawn_timeout_id = player.setTimeout(randint(600, 1200), self.set_ready)

    def step(self):
        if not self.__is_running:
            return
        self.__step_counter -= 1
        if self.__step_counter == 0:
            if self.__current_path[1] != 0:
                super(IdlePlayer, self)._change_heading(self.__current_path[1])
                self.__current_path = self.__route_iter.next()
                self.__step_counter = self.__current_path[0]
            else:
                self.set_dead(True)
                return
        super(IdlePlayer, self)._step()


class AboutPlayer(avg.DivNode):
    def __init__(self, about_data, parent=None, **kwargs):
        kwargs['sensitive'] = False
        super(AboutPlayer, self).__init__(**kwargs)
        self.registerInstance(self, parent)

        color = PLAYER_COLORS[about_data['colorIdx']]
        scale = about_data['size'] * g_grid_size

        self.__text_node = avg.WordsNode(
            parent=self, text=about_data['text'], color=color,
            font='Ubuntu', fontsize=scale, alignment='center', opacity=0
        )
        self.size = self.__text_node.size + Point2D(4, 1) * g_grid_size
        self.size = (
            ceil(self.width / g_grid_size) * g_grid_size,
            ceil(self.height / g_grid_size) * g_grid_size
        )
        self.__text_node.pos = (0, (self.height - self.__text_node.height) / 2)

        about_data['startPos'] = Point2D(-self.width / 2, self.height) / g_grid_size
        about_data['route'] = [
            (int(self.height / g_grid_size), -1),
            (int(self.width / g_grid_size), -1),
            (int(self.height / g_grid_size), -1),
            (int(self.width / g_grid_size), 0)
        ]
        self.__idle_player = IdlePlayer(about_data, parent=self)

    def set_ready(self):
        avg.Anim.fadeIn(self.__text_node, 200)
        self.__idle_player.set_ready()

    def set_dead(self, restart=False):
        self.__idle_player.set_dead()
        avg.Anim.fadeOut(self.__text_node, 200)

    def step(self):
        self.__idle_player.step()


class DragItem(avg.DivNode):
    def __init__(self, icon_node, parent=None, **kwargs):
        self._pos_offset = Point2D(g_grid_size * 8, g_grid_size * 8)
        w, h = parent.size
        kwargs['size'] = self._pos_offset * 2
        super(DragItem, self).__init__(**kwargs)
        self.registerInstance(self, parent)

        self.__active = False

        self.__min_pos_x = int(-self._pos_offset.x) + g_grid_size
        self.__max_pos_x = int(w - self._pos_offset.x)
        self.__pos_x = range(self.__min_pos_x, self.__max_pos_x, g_grid_size)
        self.__min_pos_y = int(-self._pos_offset.y) + g_grid_size
        self.__max_pos_y = int(h - self._pos_offset.y)
        self.__pos_y = range(self.__min_pos_y, self.__max_pos_y, g_grid_size)

        self.__node = icon_node
        self.__node.opacity = 0
        self.appendChild(self.__node)

        self.__cursor_id = None
        self.__drag_offset = None
        self.subscribe(avg.Node.CURSOR_DOWN, self._on_down)
        self.subscribe(avg.Node.CURSOR_UP, self.__on_up)
        self.subscribe(avg.Node.CURSOR_MOTION, self.__on_motion)

    def activate(self):
        self.__active = True
        self.__flash()

    def deactivate(self):
        self.__active = False

    def jump(self):
        self.pos = (choice(self.__pos_x), choice(self.__pos_y))

    def check_collision(self, pos):
        if self.__cursor_id is not None:
            return False  # no collision when dragging
        dist = self.pos + self._pos_offset - pos
        if abs(dist.x) <= g_grid_size and abs(dist.y) <= g_grid_size:
            return True
        return False

    def __flash(self):
        if self.__active:
            avg.LinearAnim(self.__node, 'opacity', 600, 1, 0).start()
            avg.LinearAnim(self.__node, 'fillopacity', 600, 1, 0, False, None, self.__flash).start()

    def _on_down(self, event):
        if self.__cursor_id is not None:
            return
        self.__cursor_id = event.cursorid
        self.setEventCapture(self.__cursor_id)
        self.__drag_offset = event.pos - self.pos
        return

    def __on_up(self, event):
        if self.__cursor_id != event.cursorid:
            return
        self.releaseEventCapture(self.__cursor_id)
        self.__cursor_id = None
        return

    def __on_motion(self, event):
        if self.__cursor_id != event.cursorid:
            return
        pos = (event.pos - self.__drag_offset) / g_grid_size
        pos = Point2D(round(pos.x), round(pos.y)) * g_grid_size
        if self.__min_pos_x <= pos.x < self.__max_pos_x and self.__min_pos_y <= pos.y < self.__max_pos_y:
            self.pos = pos
        return


class Shield(DragItem):
    def __init__(self, *args, **kwargs):
        icon = avg.CircleNode(r=g_grid_size * 2)
        super(Shield, self).__init__(icon, *args, **kwargs)

        icon.pos = self._pos_offset
        self.__is_grabbed = False

    def jump(self):
        super(Shield, self).jump()
        self.__is_grabbed = False

    def move(self, pos):
        self.pos = pos - self._pos_offset

    def check_collision(self, pos):
        if self.__is_grabbed:
            return False
        return super(Shield, self).check_collision(pos)

    def grab(self):
        self.__is_grabbed = True

    def _on_down(self, event):
        if self.__is_grabbed:
            return
        return super(Shield, self)._on_down(event)


class Blocker(DragItem):
    def __init__(self, *args, **kwargs):
        icon = avg.RectNode(size=(g_grid_size * 3, g_grid_size * 3), color='FF0000', fillcolor='FF0000')
        super(Blocker, self).__init__(icon, *args, **kwargs)

        icon.pos = self._pos_offset - icon.size / 2


class BgAnim(avg.DivNode):
    def __init__(self, parent=None, **kwargs):
        size = parent.size
        self.__max_x, self.__max_y = size
        kwargs['pos'] = (int(size.x / 2), int(size.y / 2))
        kwargs['opacity'] = 0.2
        super(BgAnim, self).__init__(**kwargs)
        self.registerInstance(self, parent)

        avg.LineNode(parent=self, pos1=(-self.__max_x, 0), pos2=(self.__max_x, 0))
        avg.LineNode(parent=self, pos1=(0, -self.__max_y), pos2=(0, self.__max_y))

        self.__heading = Point2D(randint(-1, 1), 0)
        if self.__heading.x == 0:
            self.__heading.y = choice([-1, 1])
        self.__heading_countdown = randint(60, 120)

    def start(self):
        player.subscribe(player.ON_FRAME, self.__on_frame)

    def stop(self):
        player.unsubscribe(player.ON_FRAME, self.__on_frame)

    def __on_frame(self):
        if self.__heading_countdown == 0:
            self.__heading_countdown = randint(60, 120)
            if self.__heading.x == 0:
                self.__heading.x = choice([-1, 1])
                self.__heading.y = 0
            else:
                self.__heading.x = 0
                self.__heading.y = choice([-1, 1])
        else:
            self.__heading_countdown -= 1

        self.pos += self.__heading
        if self.pos.x == 0 or self.pos.x == self.__max_x or self.pos.y == 0 or self.pos.y == self.__max_y:
            self.__heading *= -1
            self.pos += self.__heading


class TROff(app.MainDiv):
    def onInit(self):
        global g_grid_size
        self.mediadir = utils.getMediaDir(__file__)
        screen_size = player.getRootNode().size
        g_grid_size = int(min(floor(screen_size.x / BASE_GRID_SIZE.x), floor(screen_size.y / BASE_GRID_SIZE.y)))
        border_width = g_grid_size * BASE_BORDER_WIDTH
        battleground_size = Point2D(
            floor((screen_size.x - border_width * 2) / g_grid_size) * g_grid_size,
            floor((screen_size.y - border_width * 2) / g_grid_size) * g_grid_size
        )
        border_width = (screen_size - battleground_size) / 2.0

        avg.RectNode(parent=self, size=screen_size, opacity=0, fillcolor='B00000', fillopacity=1)
        avg.RectNode(
            parent=self, pos=border_width, size=battleground_size, opacity=0, fillcolor='000000', fillopacity=1
        )

        battleground = avg.DivNode(parent=self, pos=border_width, size=battleground_size, crop=True)

        self.__bg_anims = []
        for i in xrange(4):
            self.__bg_anims.append(BgAnim(parent=battleground))
        self.__init_idle_demo(battleground)

        self.__game_div = avg.DivNode(parent=battleground, size=battleground_size)
        self.__ctrl_div = avg.DivNode(parent=self.__game_div, size=battleground_size)
        self.__wins_div = avg.DivNode(parent=self.__ctrl_div, size=battleground_size, opacity=0, sensitive=False)

        self.__shield = Shield(parent=self.__ctrl_div)
        self.__blocker = Blocker(parent=self.__ctrl_div)

        ctrl_size = Point2D(g_grid_size * 42, g_grid_size * 42)
        player_pos = ctrl_size.x + g_grid_size * 2
        self.__controllers = []
        # 1st
        player_ = RealPlayer(
            PLAYER_COLORS[0], (player_pos, player_pos), (g_grid_size, 0),
            self.__wins_div, ctrl_size, pi, parent=self.__game_div
        )
        self.__controllers.append(Controller(
            player_, self.join_player, parent=self.__ctrl_div,
            pos=(g_grid_size, g_grid_size), size=ctrl_size, angle=0)
        )
        # 2nd
        player_ = RealPlayer(
            PLAYER_COLORS[1], (self.__ctrl_div.size.x - player_pos, player_pos), (-g_grid_size, 0),
            self.__wins_div, ctrl_size, -pi / 2, parent=self.__game_div
        )
        self.__controllers.append(Controller(
            player_, self.join_player, parent=self.__ctrl_div,
            pos=(self.__ctrl_div.size.x - g_grid_size, g_grid_size), size=ctrl_size, angle=pi / 2)
        )
        # 3rd
        player_ = RealPlayer(
            PLAYER_COLORS[2], (player_pos, self.__ctrl_div.size.y - player_pos), (g_grid_size, 0),
            self.__wins_div, ctrl_size, pi / 2, parent=self.__game_div
        )
        self.__controllers.append(Controller(
            player_, self.join_player, parent=self.__ctrl_div,
            pos=(g_grid_size, self.__ctrl_div.size.y - g_grid_size), size=ctrl_size, angle=-pi / 2)
        )
        # 4th
        player_ = RealPlayer(
            PLAYER_COLORS[3], (self.__ctrl_div.size.x - player_pos, self.__ctrl_div.size.y - player_pos),
            (-g_grid_size, 0), self.__wins_div, ctrl_size, 0, parent=self.__game_div
        )
        self.__controllers.append(Controller(
            player_, self.join_player, parent=self.__ctrl_div,
            pos=(self.__ctrl_div.size.x - g_grid_size, self.__ctrl_div.size.y - g_grid_size),
            size=ctrl_size, angle=pi)
        )

        self.__start_button = Button(self.__ctrl_div, 'FF0000', 'O', self.__start)
        self.__clear_button = Button(self.__ctrl_div, 'FF0000', '#', self.__clear_wins)
        self.__countdown_node = avg.CircleNode(
            parent=self.__ctrl_div, pos=self.__ctrl_div.size / 2, r=self.__ctrl_div.size.y / 4,
            opacity=0, sensitive=False
        )

        self.__left_quit_button = Button(self.__wins_div, 'FF0000', 'xl', player.stop)
        self.__left_quit_button.activate()
        self.__right_quit_button = Button(self.__wins_div, 'FF0000', 'xr', player.stop)
        self.__right_quit_button.activate()

        self.__red_sound = avg.SoundNode(parent=battleground, href='red.wav')
        self.__yellow_sound = avg.SoundNode(parent=battleground, href='yellow.wav')
        self.__green_sound = avg.SoundNode(parent=battleground, href='green.wav')
        self.__start_sound = avg.SoundNode(parent=battleground, href='start.wav')

        self.__down_handler_id = None
        self.__pre_start()

        self.__start_sound.play()
        self.__ctrl_div.sensitive = True
        for bg_anim in self.__bg_anims:
            bg_anim.start()

        self.__start_idle_demo()

    def join_player(self, player_):
        self.__active_players.append(player_)
        if len(self.__active_players) == 1:
            avg.Anim.fadeOut(self.__wins_div, 200)
            self.__wins_div.sensitive = False
        elif len(self.__active_players) == 2:
            self.__start_button.activate()

    def __pre_start(self, clear_wins=False):
        self.__active_players = []
        for ctrl in self.__controllers:
            ctrl.pre_start(clear_wins)
        self.__shield.jump()
        self.__blocker.jump()

    def __start(self):
        def go_green():
            self.__green_sound.play()
            self.__countdown_node.fillcolor = '00FF00'
            avg.LinearAnim(self.__countdown_node, 'fillopacity', 1000, 1, 0).start()
            for ctrl_ in self.__controllers:
                ctrl_.start()
            player.subscribe(player.ON_FRAME, self.__on_game_frame)

        def go_yellow():
            self.__yellow_sound.play()
            self.__countdown_node.fillcolor = 'FFFF00'
            avg.LinearAnim(self.__countdown_node, 'fillopacity', 1000, 1, 0, False, None, go_green).start()
            self.__shield.activate()
            self.__blocker.activate()

        def go_red():
            self.__red_sound.play()
            self.__countdown_node.fillcolor = 'FF0000'
            avg.LinearAnim(self.__countdown_node, 'fillopacity', 1000, 1, 0, False, None, go_yellow).start()

        self.__deactivate_idle_timer()
        self.__start_button.deactivate()
        for ctrl in self.__controllers:
            ctrl.deactivate_unjoined()
        go_red()

    def __stop(self, force_clear_wins=False):
        def restart():
            for player_ in self.__active_players:
                player_.set_dead(False)
            avg.Anim.fadeIn(self.__wins_div, 200)
            self.__wins_div.sensitive = True
            self.__activate_idle_timer()
            if force_clear_wins:
                self.__clear_button.activate()
            else:
                self.__pre_start()

        player.unsubscribe(player.ON_FRAME, self.__on_game_frame)
        self.__shield.deactivate()
        self.__blocker.deactivate()
        player.setTimeout(2000, restart)

    def __clear_wins(self):
        self.__start_sound.play()
        self.__clear_button.deactivate()
        self.__pre_start(True)

    def __on_game_frame(self):
        for player_ in self.__active_players:
            player_.step()

        crashed_players = []
        for player_ in self.__active_players:
            if player_.check_crash(self.__active_players, self.__blocker):
                crashed_players.append(player_)
        for player_ in crashed_players:
            player_.set_dead()
            self.__active_players.remove(player_)

        if len(self.__active_players) == 0:
            self.__stop()
        elif len(self.__active_players) == 1:
            self.__active_players[0].inc_wins()
            if self.__active_players[0].wins == 8:
                self.__stop(True)
            else:
                self.__stop()
        else:
            for player_ in self.__active_players:
                player_.check_shield(self.__shield)

    def __init_idle_demo(self, parent):
        self.__idle_timeout_id = None
        self.__idle_players = []

        with open(getMediaDir(__file__, 'data/idledemo.pickle'), 'r') as fp:
            demo_data = load(fp)
        demo_div = avg.DivNode(parent=parent, pos=parent.size / 2 - Point2D(0, g_grid_size * 20))
        for data in demo_data:
            self.__idle_players.append(IdlePlayer(data, parent=demo_div))

        with open(getMediaDir(__file__, 'data/idleabout.pickle'), 'r') as fp:
            about_data = load(fp)
        about_div = avg.DivNode(parent=parent, pos=parent.size / 2 - Point2D(0, g_grid_size * 10))
        pos = Point2D(0, 0)
        for data in about_data:
            about_player = AboutPlayer(data, parent=about_div, pos=pos)
            pos.y += about_player.height + 4 * g_grid_size
            self.__idle_players.append(about_player)

    def __activate_idle_timer(self):
        assert self.__idle_timeout_id is None
        self.__idle_timeout_id = player.setTimeout(IDLE_TIMEOUT, self.__start_idle_demo)
        self.__down_handler_id = self.__ctrl_div.subscribe(
            avg.Node.CURSOR_DOWN, lambda e: self.__restart_idle_timer()
        )

    def __deactivate_idle_timer(self):
        assert self.__idle_timeout_id is not None
        player.clearInterval(self.__idle_timeout_id)
        self.__idle_timeout_id = None
        if self.__down_handler_id is not None:
            self.__ctrl_div.unsubscribe(self.__down_handler_id)

    def __restart_idle_timer(self):
        if self.__idle_timeout_id is not None:
            player.clearInterval(self.__idle_timeout_id)
        self.__idle_timeout_id = player.setTimeout(IDLE_TIMEOUT, self.__start_idle_demo)

    def __start_idle_demo(self):
        self.__idle_timeout_id = None
        avg.Anim.fadeOut(self.__game_div, 200)
        self.__ctrl_div.sensitive = False
        for player_ in self.__idle_players:
            player_.set_ready()
        self.__demo_down_handler_id = self.__game_div.subscribe(
            avg.Node.CURSOR_DOWN, lambda e: self.__stop_idle_demo()
        )
        player.subscribe(player.ON_FRAME, self.__on_idle_frame)

    def __stop_idle_demo(self):
        self.__game_div.unsubscribe(self.__demo_down_handler_id)
        player.unsubscribe(player.ON_FRAME, self.__on_idle_frame)
        avg.Anim.fadeIn(self.__game_div, 200)
        self.__ctrl_div.sensitive = True
        for player_ in self.__idle_players:
            player_.set_dead()
        self.__restart_idle_timer()

    def __on_idle_frame(self):
        for player_ in self.__idle_players:
            player_.step()


if __name__ == '__main__':
    app.App().run(TROff())
