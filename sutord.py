#!/usr/bin/env python3

import random
from enum import Enum, auto
from collections import Counter
from pathlib import Path
import json
from unidecode import unidecode
import discord

class LetterType(Enum):
    FOUND = auto()
    EXIST = auto()
    WRONG = auto()

class Action(Enum):
    JOIN = '🆗'
    PLAY = '▶️'
    STOP = '⏹️'

def rank_to_emojis(rank):
    digits = [':zero:', ':one:', ':two:', ':three:', ':four:', ':five:', ':six:', ':seven:', ':eight:', ':nine:']

    if rank < 1:
        return ':interrobang:'
    elif rank == 1:
        return ':first_place:'
    elif rank == 2:
        return ':second_place:'
    elif rank == 3:
        return ':third_place:'
    else:
        return ''.join(digits[i] for i in map(int, str(rank)))

def letter_to_emojis(letter):
    return f':regional_indicator_{letter}:' if letter is not None else ':blue_square:'

def letters_to_emojis(letters):
    return ' '.join(map(letter_to_emojis, letters))

def type_to_emojis(type):
    if type == LetterType.FOUND:
        return ':red_square:'
    elif type == LetterType.EXIST:
        return ':yellow_square:'
    elif type == LetterType.WRONG:
        return ':blue_square:'

def types_to_emojis(types):
    return ' '.join(map(type_to_emojis, types))

def join(seq, sep, sep_last):
    return sep.join(seq[:-1]) + sep_last + seq[-1] if len(seq) > 1 else seq[0]

def split(message, limit=2000):
    lines = message.split('\n')
    it = iter(lines)
    current = next(it)

    for line in it:
        if len(current) + len(line) < limit:
            current += f'\n{line}'
        else:
            yield current
            current = line

    yield current

async def send_long_message(channel, message):
    for msg in split(message):
        await channel.send(msg)

class Dictionary:
    def __init__(self, dictionary, choices):
        self.dictionary = self.load(dictionary, set)
        self.choices = self.load(choices, list)

        self.dictionary.update(self.choices)

    def choice(self):
        return random.choice(self.choices)

    def contains(self, word):
        return word in self.dictionary

    @staticmethod
    def normalize(word):
        return ''.join(filter(str.isalpha, unidecode(word))).lower()

    @staticmethod
    def load(filename, type):
        with open(filename) as file:
            return type(map(Dictionary.normalize, file))

class Answer:
    def __init__(self, word, hidden_word):
        self.letters = word
        self.types = self.check(word, hidden_word)

    def get_emojis(self, letters=True):
        if letters:
            return f'{letters_to_emojis(self.letters)}\n{types_to_emojis(self.types)}'
        else:
            return types_to_emojis(self.types)

    def get_letters_found(self):
        return (x if y == LetterType.FOUND else None for x, y in zip(self.letters, self.types))

    @staticmethod
    def check(word, hidden_word):
        types = []
        counts = Counter(hidden_word)

        for x, y in zip(word, hidden_word):
            if x == y:
                counts[x] -= 1

        for x, y in zip(word, hidden_word):
            if x == y:
                types.append(LetterType.FOUND)
            elif x in hidden_word and counts[x] > 0:
                types.append(LetterType.EXIST)
                counts[x] -= 1
            else:
                types.append(LetterType.WRONG)

        return types

class Player:
    def __init__(self, user, hidden_word):
        self.mention = user.mention
        self.rank = -1
        self.left = False
        self.letters = [x if i == 0 else None for i, x in enumerate(hidden_word)]
        self.answers = []

    def get_header_emojis(self):
        emoji = ':wave:' if self.left else rank_to_emojis(self.rank)
        return f'{emoji} {self.mention}'

    def get_letters_emojis(self):
        return letters_to_emojis(self.letters)

    def get_answer_emojis(self, index=-1, letters=True):
        return self.answers[index].get_emojis(letters)

    def get_all_answers_emojis(self, letters=True):
        return '\n'.join(answer.get_emojis(letters) for answer in self.answers)

    def found(self):
        return None not in self.letters

    def over(self):
        return self.found() or self.left

    def answered(self):
        return len(self.answers) > 0

    def add_answer(self, word, hidden_word):
        answer = Answer(word, hidden_word)
        self.letters = [x or y for x, y in zip(self.letters, answer.get_letters_found())]
        self.answers.append(answer)

class Game:
    def __init__(self, dictionary, users):
        self.dictionary = dictionary
        self.hidden_word = dictionary.choice()
        self.players = { user : Player(user, self.hidden_word) for user in users }
        self.next_rank = 1

    def get_all_mentions_emojis(self):
        mentions = [player.mention for player in self.players.values()]
        return join(mentions, ', ', ' et ')

    def get_player(self, user):
        return self.players[user]

    def get_sorted_players(self):
        return sorted(self.players.values(), key=lambda player: player.rank if player.rank > 0 else self.next_rank)

    def over(self):
        return all(player.over() for player in self.players.values())

    def answered(self):
        return any(player.answered() for player in self.players.values())

    def add_player(self, user):
        if user in self.players:
            return False

        self.players[user] = Player(user, self.hidden_word)

        return True

    def remove_player(self, user):
        if user not in self.players or self.players[user].over():
            return False

        self.players[user].left = True

        return True

    def add_answer(self, user, word):
        if user not in self.players:
            return False, None

        player = self.players[user]

        if player.over():
            return False, None

        word = self.dictionary.normalize(word)

        if len(word) < len(self.hidden_word):
            return False, 'Le mot proposé est trop court.'
        elif len(word) > len(self.hidden_word):
            return False, 'Le mot proposé est trop long.'
        elif not self.dictionary.contains(word):
            return False, 'Le mot proposé n\'est pas dans le dictionnaire.'
        else:
            player.add_answer(word, self.hidden_word)

        if player.found():
            player.rank = self.next_rank
            self.next_rank += 1

        return True, None

class PlayerStats:
    def __init__(self):
        self.ranks = Counter()
        # self.num_played = sum(ranks.values())
        # self.num_not_found = ranks[-1]
        # self.num_found = self.num_played - self.num_not_found
        self.words = Counter()
        # self.num_words = sum(words.values())
        # self.num_unique_words = len(self.words)
        # self.n_most_used = self.words.most_common(n)
        self.num_words_when_found = 0
        # self.mean_num_words_when_found = self.num_words_when_found / self.num_found

    def get_emojis(self):
        num_played = sum(self.ranks.values())
        num_not_found = self.ranks[-1]
        num_found = num_played - num_not_found
        if num_found == 0:
            return 'Vous n\'avez pas encore trouvé de mots !'

        percentage_found = 100 * num_found / num_played

        medals_emojis = ' '.join(f'{rank_to_emojis(rank)} {self.ranks[rank]}' for rank in range(1, 4))

        num_words = sum(self.words.values())
        num_unique_words = len(self.words)
        most_used_words_emojis = join([f'{word} ({num})' for word, num in self.words.most_common(5)], ', ', ' et ')

        mean_num_words_when_found = self.num_words_when_found / num_found

        return (f'Vous avez joué {num_played} parties, dont {percentage_found:.2f}% de réussite.\n'
                f'Votre liste de médailles est : {medals_emojis}\n'
                f'Vous avez essayé {num_words} mots, dont {num_unique_words} mots uniques.\n'
                f'Vos mots les plus utilisés sont : {most_used_words_emojis}.\n'
                f'Votre nombre d\'essais moyen pour trouver est de {mean_num_words_when_found:.2f} mots.')

    def update(self, player):
        self.ranks[player.rank] += 1
        self.words.update(answer.letters for answer in player.answers)
        if player.found():
            self.num_words_when_found += len(player.answers)

    def save(self, filename):
        with open(filename, 'w') as file:
            file.write(f'{json.dumps(self.ranks)}\n')
            file.write(f'{json.dumps(self.words)}\n')
            file.write(f'{self.num_words_when_found}\n')

    @staticmethod
    def load(filename):
        player_stats = PlayerStats()

        if Path(filename).is_file():
            with open(filename, 'r') as file:
                player_stats.ranks = Counter({ int(rank) : num for rank, num in json.loads(file.readline()).items() })
                player_stats.words = Counter(json.loads(file.readline()))
                player_stats.num_words_when_found = int(file.readline())

        return player_stats

class GamesStats:
    def __init__(self):
        self.hidden_words = Counter()
        # self.num_games = sum(self.hidden_words.values())
        self.num_players = 0
        # self.mean_num_players = self.num_players / self.num_games

    def get_emojis(self):
        num_games = sum(self.hidden_words.values())
        if num_games == 0:
            return 'Aucune partie n\'a été jouée !'

        mean_num_players = self.num_players / num_games

        repeated_hidden_words = [word for word, num in self.hidden_words.items() if num > 1]
        repeated_hidden_words_emojis = join(repeated_hidden_words, ', ', ' et ') if repeated_hidden_words else 'aucun !'

        return (f'Un total de {num_games} parties ont été jouées.\n'
                f'Le nombre moyen de joueurs par partie est de {mean_num_players:.2f}.\n'
                f'Les mots à trouver étant apparus plusieurs fois sont : {repeated_hidden_words_emojis}')

    def update(self, game):
        self.hidden_words[game.hidden_word] += 1
        self.num_players += len(game.players)

    def save(self, filename):
        with open(filename, 'w') as file:
            file.write(f'{json.dumps(self.hidden_words)}\n')
            file.write(f'{self.num_players}\n')

    @staticmethod
    def load(filename):
        games_stats = GamesStats()

        if Path(filename).is_file():
            with open(filename, 'r') as file:
                games_stats.hidden_words = Counter(json.loads(file.readline()))
                games_stats.num_players = int(file.readline())

        return games_stats

class Stats:
    def __init__(self, folder):
        self.folder = folder
        self.games_stats = GamesStats.load(self.get_games_stats_filename())
        self.players_stats = {}

    def get_games_stats_filename(self):
        return f'{self.folder}/games.txt'

    def get_player_stats_filename(self, user):
        return f'{self.folder}/{user.id}.txt'

    def get_player_stats_emojis(self, user):
        if user not in self.players_stats:
            self.players_stats[user] = PlayerStats.load(self.get_player_stats_filename(user))

        return self.players_stats[user].get_emojis()

    def update(self, game):
        self.games_stats.update(game)

        for user, player in game.players.items():
            if user not in self.players_stats:
                self.players_stats[user] = PlayerStats.load(self.get_player_stats_filename(user))

            self.players_stats[user].update(player)

    def save(self):
        self.games_stats.save(self.get_games_stats_filename())

        for user, player_stats in self.players_stats.items():
            player_stats.save(self.get_player_stats_filename(user))

class Client(discord.Client):
    def __init__(self, intents):
        super().__init__(intents=intents)

        self.sutom_dictionary = Dictionary('dictionary.txt', 'choices.txt')
        self.sutom_stats = Stats('stats')

        self.sutom_message = None
        self.sutom_game = None

    async def on_sutom(self, message):
        if self.sutom_message:
            await message.channel.send('Une partie est déjà en cours.', reference=message)
            return

        self.sutom_message = message
        self.sutom_game = None

        await self.change_presence(activity=discord.Game(name='sutom'))
        await message.add_reaction(Action.JOIN.value)
        await message.add_reaction(Action.PLAY.value)
        await message.add_reaction(Action.STOP.value)

    async def sutom_join(self, user):
        if self.sutom_game:
            added = self.sutom_game.add_player(user)
            if added:
                await self.sutom_message.channel.send(f'{user.mention} rejoint la partie. Bonne chance !')
                await user.send(self.sutom_game.get_player(user).get_letters_emojis())

    async def sutom_start(self):
        if self.sutom_game:
            return

        users = []

        for reaction in self.sutom_message.reactions:
            if reaction.emoji == Action.JOIN.value:
                users = await reaction.users().flatten()
                users = list(filter(lambda user: user != self.user, users))

        self.sutom_game = Game(self.sutom_dictionary, users)

        mentions_emojis = f'Bonne chance {self.sutom_game.get_all_mentions_emojis()} !' if users else 'Aucun joueur ne l\'a encore rejointe !'
        await self.sutom_message.channel.send(f'La partie commence ! {mentions_emojis}')

        for user in users:
            await user.send(self.sutom_game.get_player(user).get_letters_emojis())

    async def sutom_stop(self):
        if not self.sutom_game:
            await self.sutom_message.channel.send('La partie n\'était pas encore commencée qu\'elle se termine déjà.')
        else:
            await self.sutom_message.channel.send(f'La partie est terminée ! Le mot à trouver était {self.sutom_game.hidden_word}.')
            if not self.sutom_game.answered():
                await self.sutom_message.channel.send('Aucun joueur n\'a donné de réponse.')
            else:
                for player in self.sutom_game.get_sorted_players():
                    if player.answered():
                        emojis = f'{player.get_header_emojis()}\n{player.get_all_answers_emojis()}'
                        await send_long_message(self.sutom_message.channel, emojis)

                self.sutom_stats.update(self.sutom_game)
                self.sutom_stats.save()

        await self.change_presence()

        self.sutom_message = None
        self.sutom_game = None

    async def on_reaction_add(self, reaction, user):
        if not self.sutom_message or self.sutom_message != reaction.message or user == self.user:
            return

        if reaction.emoji == Action.JOIN.value:
            await self.sutom_join(user)
        elif reaction.emoji == Action.PLAY.value and user == self.sutom_message.author:
            await self.sutom_start()
        elif reaction.emoji == Action.STOP.value and user == self.sutom_message.author:
            await self.sutom_stop()

    async def sutom_leave(self, user):
        if self.sutom_game:
            removed = self.sutom_game.remove_player(user)
            if removed:
                await self.sutom_message.channel.send(f'{user.mention} quitte la partie.')

                if self.sutom_game.over():
                    await self.sutom_stop()

    async def on_reaction_remove(self, reaction, user):
        if not self.sutom_message or self.sutom_message != reaction.message or user == self.user:
            return

        if reaction.emoji == Action.JOIN.value:
            await self.sutom_leave(user)

    async def on_message_delete(self, message):
        if not self.sutom_message or self.sutom_message != message:
            return

        await self.sutom_stop()

    async def on_sutom_answer(self, message):
        if not self.sutom_game:
            return

        added, error = self.sutom_game.add_answer(message.author, message.content)
        if not added:
            if error:
                await message.channel.send(error)
            return

        player = self.sutom_game.get_player(message.author)
        answer_emojis = player.get_answer_emojis()
        letters_emojis = player.get_letters_emojis()

        if letters_emojis not in answer_emojis:
            await message.channel.send(f'{answer_emojis}\n{letters_emojis}')
        else:
            await message.channel.send(answer_emojis)

        if player.found():
            await message.channel.send('Félicitations, vous avez trouvé le mot !')
            await send_long_message(self.sutom_message.channel, f'{player.get_header_emojis()}\n{player.get_all_answers_emojis(False)}')

            if self.sutom_game.over():
                await self.sutom_stop()

    async def on_sutom_stats(self, message):
        await message.channel.send(self.sutom_stats.get_player_stats_emojis(message.author), reference=message)

    async def on_sutom_stats_games(self, message):
        await message.channel.send(self.sutom_stats.games_stats.get_emojis(), reference=message)

    async def on_message(self, message):
        if message.author == self.user:
            return

        content = message.content.lower()

        if isinstance(message.channel, discord.DMChannel):
            await self.on_sutom_answer(message)
        else:
            if content == 'sutom':
                await self.on_sutom(message)
            elif content == 'sutom stats':
                await self.on_sutom_stats(message)
            elif content == 'sutom stats games':
                await self.on_sutom_stats_games(message)

intents = discord.Intents.default()
intents.members = True

client = Client(intents=intents)
client.run(Path('token.txt').read_text())
