# -*- coding: utf-8 -*-
import re
from os.path import join, abspath, dirname
import eng_to_ipa.stress as stress
from collections import defaultdict


class ModeType(object):
    sqlite_mode = None
    json_mode = None

    @staticmethod
    def get_mode(mode):
        if mode.lower() == "sql":
            if ModeType.sqlite_mode is None:
                import sqlite3
                conn = sqlite3.connect(join(abspath(dirname(__file__)),
                                            "./resources/CMU_dict.db"))
                ModeType.sqlite_mode = conn.cursor()
            return ModeType.sqlite_mode
        elif mode.lower() == "json":
            if ModeType.json_mode is None:
                import json
                json_file = open(join(abspath(dirname(__file__)),
                                    "../eng_to_ipa/resources/CMU_dict.json"),
                                encoding="UTF-8")
                ModeType.json_mode = json.load(json_file)   
            return ModeType.json_mode
        else:
            raise Exception("Invalid mode: " + mode)


def preprocess(words):
    """Returns a string of words stripped of punctuation"""
    punct_str = '!"#$%&\'()*+,-./:;<=>/?@[\\]^_`{|}~«» '
    return ' '.join([w.strip(punct_str).lower() for w in words.split()])


def preserve_punc(words):
    """converts words to IPA and finds punctuation before and after the word."""
    words_preserved = []
    for w in words.split():
        punct_list = ["", preprocess(w), ""]
        before = re.search(r"^([^A-Za-z0-9]+)[A-Za-z]", w)
        after = re.search(r"[A-Za-z]([^A-Za-z0-9]+)$", w)
        if before:
            punct_list[0] = str(before.group(1))
        if after:
            punct_list[2] = str(after.group(1))
        words_preserved.append(punct_list)
    return words_preserved


def apply_punct(triple, as_str=False):
    """places surrounding punctuation back on center on a list of preserve_punc triples"""
    if type(triple[0]) == list:
        for i, t in enumerate(triple):
            triple[i] = str(''.join(triple[i]))
        if as_str:
            return ' '.join(triple)
        return triple
    if as_str:
        return str(''.join(t for t in triple))
    return [''.join(t for t in triple)]


def _punct_replace_word(original, transcription):
    """Get the IPA transcription of word with the original punctuation marks"""
    for i, trans_list in enumerate(transcription):
        for j, item in enumerate(trans_list):
            triple = [original[i][0]] + [item] + [original[i][2]]
            transcription[i][j] = apply_punct(triple, as_str=True)
    return transcription


def fetch_words(words_in, db_type="sql"):
    """fetches a list of words from the database"""
    asset = ModeType.get_mode(db_type)
    if db_type.lower() == "sql":
        quest = "?, " * len(words_in)
        asset.execute("SELECT word, phonemes FROM dictionary "
                      "WHERE word IN ({0})".format(quest[:-2]), words_in)
        result = asset.fetchall()
        d = defaultdict(list)
        for k, v in result:
            d[k].append(v)
        return list(d.items())
    if db_type.lower() == "json":
        words = []
        for word in set(words_in):
            if word in asset:
                words.append((word, asset[word]))
        return words


def get_cmu(tokens_in, db_type="sql"):
    """query the SQL database for the words and return the phonemes in the order of user_in"""
    result = fetch_words(tokens_in, db_type)
    ordered = []
    for word in tokens_in:
        cmu = next(filter(lambda x: x[0] == word, result), None)
        if cmu is not None:
            ordered.append(cmu[1])
        else:
            ordered.append(["__IGNORE__" + word])
    return ordered


def cmu_to_ipa(cmu_list, mark=True, stress_marking='all'):
    """converts the CMU word lists into IPA transcriptions"""
    symbols = {"a": "ə", "ey": "eɪ", "aa": "ɑ", "ae": "æ", "ah": "ə", "ao": "ɔ",
               "aw": "aʊ", "ay": "aɪ", "ch": "ʧ", "dh": "ð", "eh": "ɛ", "er": "ər",
               "hh": "h", "ih": "ɪ", "jh": "ʤ", "ng": "ŋ",  "ow": "oʊ", "oy": "ɔɪ",
               "sh": "ʃ", "th": "θ", "uh": "ʊ", "uw": "u", "zh": "ʒ", "iy": "i", "y": "j"}
    final_list = []  # the final list of IPA tokens to be returned
    for word_list in cmu_list:
        ipa_word_list = []  # the word list for each word
        for word in word_list:
            if stress_marking:
                word = stress.find_stress(word, type=stress_marking)
            else:
                if re.sub(r"\d*", "", word.replace("__IGNORE__", "")) == "":
                    pass  # do not delete token if it's all numbers
                else:
                    word = re.sub("[0-9]", "", word)
            ipa_form = ''
            if word.startswith("__IGNORE__"):
                ipa_form = word.replace("__IGNORE__", "")
                # mark words we couldn't transliterate with an asterisk:
                if mark:
                    if not re.sub(r"\d*", "", ipa_form) == "":
                        ipa_form += "*"
            else:
                for piece in word.split(" "):
                    marked = False
                    unmarked = piece
                    if piece[0] in ["ˈ", "ˌ"]:
                        marked = True
                        mark = piece[0]
                        unmarked = piece[1:]
                    if unmarked in symbols:
                        if marked:
                            ipa_form += mark + symbols[unmarked]
                        else:
                            ipa_form += symbols[unmarked]

                    else:
                        ipa_form += piece
            swap_list = [["ˈər", "əˈr"], ["ˈie", "iˈe"]]
            for sym in swap_list:
                if not ipa_form.startswith(sym[0]):
                    ipa_form = ipa_form.replace(sym[0], sym[1])
            ipa_word_list.append(ipa_form)
        final_list.append(list(dict.fromkeys(ipa_word_list))) # preserving order while remove duplications
    return final_list


def get_top(ipa_list):
    """Returns only the one result for a query. If multiple entries for words are found, only the first is used."""
    return ' '.join([word_list[-1] for word_list in ipa_list])


def get_all(ipa_list):
    """utilizes an algorithm to discover and return all possible combinations of IPA transcriptions"""
    final_size = 1
    for word_list in ipa_list:
        final_size *= len(word_list)
    list_all = ["" for s in range(final_size)]
    for i in range(len(ipa_list)):
        if i == 0:
            swtich_rate = final_size / len(ipa_list[i])
        else:
            swtich_rate /= len(ipa_list[i])
        k = 0
        for j in range(final_size):
            if (j+1) % int(swtich_rate) == 0:
                k += 1
            if k == len(ipa_list[i]):
                k = 0
            list_all[j] = list_all[j] + ipa_list[i][k] + " "
    return sorted([sent[:-1] for sent in list_all])

def remove_stress_marks(ipas, stress='both'):
    if ipas:
        if stress == "primary" or stress == "none" or not stress:
            ipas = [ipa.replace("ˈ", "") for ipa in ipas]
        if stress == "primary" or stress == "none" or not stress:
            ipas = [ipa.replace("ˌ", "") for ipa in ipas]
    return ipas

def ipa_list(words_in, custom_ipa_dict={}, keep_punct=True, stress_marks='both', db_type="sql"):
    """Returns a list of all the discovered IPA transcriptions for each word."""
    words = [preserve_punc(w.lower())[0] for w in words_in.split()] \
        if type(words_in) == str else [preserve_punc(w.lower())[0] for w in words_in]
    custom_ipa = [custom_ipa_dict.get(w[1], None) for w in words]
    custom_ipa = [remove_stress_marks(i, stress_marks) for i in custom_ipa]
    cmu = get_cmu([w[1] for w in words], db_type=db_type)
    ipa = cmu_to_ipa(cmu, stress_marking=stress_marks)
    ipa = [i_custom or i for i_custom, i in zip(custom_ipa, ipa)]
    if keep_punct:
        ipa = _punct_replace_word(words, ipa)
    return ipa


def isin_cmu(word, db_type="sql"):
    """checks if a word is in the CMU dictionary. Doesn't strip punctuation.
    If given more than one word, returns True only if all words are present."""
    if type(word) == str:
        word = [preprocess(w) for w in word.split()]
    results = fetch_words(word, db_type)
    as_set = list(set(t[0] for t in results))
    return len(as_set) == len(set(word))


def contains(ipa, db_type="sql"):
    """Get any words that contain the IPA string. Returns the word and the IPA as a list."""
    asset = ModeType.get_mode(db_type)
    if db_type.lower() == "sql":
        asset.execute("SELECT word, ipa FROM eng_ipa WHERE "
                      "REPLACE(REPLACE(ipa, 'ˌ', ''), 'ˈ', '') "
                      "LIKE \"%{}%\"".format(str(ipa)))
        return [list(res) for res in asset.fetchall()]


def convert(text, custom_ipa_dict={}, retrieve_all=False, keep_punct=True, stress_marks='both', mode="sql"):
    """takes either a string or list of English words and converts them to IPA"""
    ipa = ipa_list(words_in=text, custom_ipa_dict=custom_ipa_dict, keep_punct=keep_punct,
                   stress_marks=stress_marks, db_type=mode)
    return get_all(ipa) if retrieve_all else get_top(ipa)


def jonvert(text, retrieve_all=False, keep_punct=True, stress_marks='both'):
    """Forces use of JSON database for fetching phoneme data."""
    return convert(text, retrieve_all, keep_punct, stress_marks, mode="json")
