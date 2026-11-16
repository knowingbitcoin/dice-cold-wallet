"""Textos de la pantalla en tres idiomas: español (es), inglés (en) y portugués de Brasil (pt).

Aquí no hay nada secreto: solo los textos fijos de la interfaz. Las palabras de
la frase son siempre las de la lista BIP39 en inglés, sea cual sea el idioma de
la pantalla: es el estándar y lo que esperan las demás carteras.

El español es el idioma de partida y el que se usa si no se pide otro. Cada
texto tiene la misma clave y los mismos huecos ({total}, {position}…) en los
tres idiomas; las pruebas lo comprueban, y también que todo cabe en 240x240.
"""

from __future__ import annotations

import string

LANGUAGES = ("en", "es", "pt")
DEFAULT_LANGUAGE = "es"

STRINGS: dict[str, dict[str, str]] = {
    "es": {
        # Pantallas de bloqueo y de error (no llevan datos).
        "error.title": "Algo ha fallado",
        "error.body": "Apaga el aparato y vuelve a empezar.",
        "network.title": "Hay una conexión de red",
        "network.body": (
            "Una cartera fría no puede tener red. Desconecta el adaptador, "
            "apaga y vuelve a encender."
        ),
        # Empezar de nuevo (KEY2).
        "reset.title": "¿Empezar de nuevo?",
        "reset.body": "Se borra todo lo que has hecho.",
        "reset.no": "No",
        "reset.yes": "Sí, borrar",
        "help.choose_accept": "◀ ▶ elegir · Pulsa: aceptar",
        "key2.start_over": "KEY2: empezar de nuevo",
        # Bienvenida.
        "welcome.title": "Cartera fría",
        "welcome.offline": "Sin red.",
        "welcome.stores_nothing": "No guarda nada.",
        "welcome.how_many": "¿Cuántas palabras?",
        "welcome.help": "◀ ▶ elegir · Pulsa: empezar",
        # Tiradas.
        "rolls.of_total": "de {total}",
        "rolls.for": "Tiradas para",
        "rolls.words": "{words} palabras",
        "rolls.help": "Pulsa: añadir · KEY3: borrar la última",
        # Revisión de las tiradas.
        "review.title": "Tiradas {first} a {last}",
        "review.editing": "Cambias la {n} · KEY3: deshacer",
        "review.compare": "Compáralas con tu papel",
        "review.help_editing": "▲ ▼ cambiar · Pulsa: guardar",
        "review.help": "Pulsa: cambiar · KEY1: todo bien, seguir",
        # Confirmación de las tiradas.
        "confirm.question": "¿Has comparado las {total} tiradas con tu papel?",
        "confirm.body": (
            "Las tiradas son tu frase. Guarda ese papel igual de bien que la frase "
            "o destrúyelo al terminar."
        ),
        "confirm.yes": "Sí, seguir",
        "confirm.no": "No, revisar",
        # Tiradas que no parecen al azar.
        "bad.title": "Estas tiradas no parecen al azar",
        "bad.face_share": "Una cara sale en más del 30 % de las tiradas.",
        "bad.long_run": "Hay demasiadas tiradas iguales seguidas.",
        "bad.body": (
            "Tira el dado de verdad para cada número. Corrige las tiradas o empieza "
            "de nuevo con KEY2."
        ),
        "bad.help": "Pulsa: volver a las tiradas",
        # Aviso antes de enseñar la frase.
        "warning.title": "Que nadie vea la pantalla",
        "warning.body": (
            "Ten a mano papel y lápiz. Vas a ver {n} palabras. "
            "Después te las preguntaré todas, mirando tu papel."
        ),
        "warning.help": "Pulsa: ver las palabras",
        # Frase.
        "phrase.title": "Palabras {first} a {last} de {total}",
        "phrase.copy": "Copia estas palabras en papel",
        "phrase.fix": "Corrige tu papel",
        "phrase.review": "Repasa tu papel",
        "phrase.help_fix": "◀ ▶ páginas · Pulsa: volver al examen",
        "phrase.help_review": "◀ ▶ páginas · Pulsa: terminar el repaso",
        "phrase.help_next": "◀ atrás · ▶ o Pulsa: siguientes",
        "phrase.help_last": "◀ atrás · Pulsa: ir al examen",
        # Examen.
        "exam.title": "Examen: {n} de {total}",
        "exam.question": "Mira tu papel. ¿Cuál es la {position}?",
        "exam.not_on_paper": "KEY3: no está en mi papel",
        "exam.help": "▲ ▼ elegir · Pulsa: responder",
        "fail.title": "Revisa la palabra {position}",
        "fail.body": "Mira esa palabra en la pantalla y corrige tu papel. Después sigue el examen.",
        "fail.help": "Pulsa: ver la palabra",
        "passed.title": "Examen aprobado",
        "passed.match": "Tu papel coincide.",
        "passed.note": "Si sigues al QR, la frase se borra y ya no podrás verla.",
        "passed.review": "Repasar las palabras",
        "passed.continue": "Seguir al QR",
        "passed.help": "▲ ▼ elegir · Pulsa: aceptar",
        # Cálculo de la clave pública.
        "deriving.title": "Calculando la clave pública…",
        "deriving.body": "Se calcula dos veces, de dos formas distintas. Espera unos segundos.",
        "mismatch.title": "Los cálculos no coinciden",
        "mismatch.body": "No uses esta cartera ni este aparato. No envíes dinero. Apágalo.",
        # QR y comprobación.
        "qr.zpub": "zpub (BlueWallet)",
        "qr.descriptor": "Descriptor · {fingerprint}",
        "check.title": "Compara con tu iPhone",
        "check.first_address": "Primera dirección de cobro",
        "check.fingerprint": "Huella, si usaste el descriptor",
        "check.zpub_note": "Con zpub, compara la dirección.",
        "check.help": "◀ volver al QR · Pulsa: terminar",
        # Fin.
        "end.title": "Apaga el aparato",
        "end.body": "La semilla se borra al quitar la corriente.",
        "end.paper": "Guarda el papel de las tiradas como la frase, o destrúyelo.",
        # Simulador y capturas.
        "sim.title": "Cartera fría · simulador",
        "sim.banner": "SIMULADOR · SOLO PRUEBAS · NO USAR CON DINERO",
        "shots.band": "SEMILLA DE PRUEBA — NO USAR",
    },
    "en": {
        "error.title": "Something went wrong",
        "error.body": "Switch the device off and start again.",
        "network.title": "Network connection found",
        "network.body": (
            "A cold wallet must stay offline. Unplug the adapter, "
            "then switch the device off and on again."
        ),
        "reset.title": "Start over?",
        "reset.body": "Everything you have done will be erased.",
        "reset.no": "No",
        "reset.yes": "Yes, erase",
        "help.choose_accept": "◀ ▶ choose · Press: OK",
        "key2.start_over": "KEY2: start over",
        "welcome.title": "Cold wallet",
        "welcome.offline": "No network.",
        "welcome.stores_nothing": "Stores nothing.",
        "welcome.how_many": "How many words?",
        "welcome.help": "◀ ▶ choose · Press: start",
        "rolls.of_total": "of {total}",
        "rolls.for": "Rolls for",
        "rolls.words": "{words} words",
        "rolls.help": "Press: add · KEY3: delete last",
        "review.title": "Rolls {first} to {last}",
        "review.editing": "Changing roll {n} · KEY3: undo",
        "review.compare": "Compare them with your paper",
        "review.help_editing": "▲ ▼ change · Press: save",
        "review.help": "Press: change · KEY1: all good, go on",
        "confirm.question": "Have you compared the {total} rolls with your paper?",
        "confirm.body": (
            "The rolls are your phrase. Keep that paper as safe as the phrase, "
            "or destroy it when you finish."
        ),
        "confirm.yes": "Yes, go on",
        "confirm.no": "No, review",
        "bad.title": "These rolls do not look random",
        "bad.face_share": "One face comes up in more than 30% of the rolls.",
        "bad.long_run": "Too many identical rolls in a row.",
        "bad.body": (
            "Actually roll the die for every number. Correct the rolls or start "
            "over with KEY2."
        ),
        "bad.help": "Press: back to the rolls",
        "warning.title": "Let no one see the screen",
        "warning.body": (
            "Get paper and a pencil to copy {n} words. "
            "Then I will ask you for each one; answer from your paper."
        ),
        "warning.help": "Press: show the words",
        "phrase.title": "Words {first} to {last} of {total}",
        "phrase.copy": "Copy these words onto paper",
        "phrase.fix": "Correct your paper",
        "phrase.review": "Go over your paper",
        "phrase.help_fix": "◀ ▶ pages · Press: back to the quiz",
        "phrase.help_review": "◀ ▶ pages · Press: end the review",
        "phrase.help_next": "◀ back · ▶ or Press: next",
        "phrase.help_last": "◀ back · Press: go to the quiz",
        "exam.title": "Quiz: {n} of {total}",
        "exam.question": "Look at your paper. Word {position}?",
        "exam.not_on_paper": "KEY3: not on my paper",
        "exam.help": "▲ ▼ choose · Press: answer",
        "fail.title": "Check word {position}",
        "fail.body": "Look at that word on the screen and correct your paper. Then go on with the quiz.",
        "fail.help": "Press: show the word",
        "passed.title": "Quiz passed",
        "passed.match": "Your paper matches.",
        "passed.note": "If you go on to the QR, the phrase is erased and you cannot see it again.",
        "passed.review": "Go over the words",
        "passed.continue": "Go on to the QR",
        "passed.help": "▲ ▼ choose · Press: OK",
        "deriving.title": "Computing the public key…",
        "deriving.body": "It is computed twice, in two different ways. Wait a few seconds.",
        "mismatch.title": "The calculations do not match",
        "mismatch.body": "Do not use this wallet or this device. Do not send money. Switch it off.",
        "qr.zpub": "zpub (BlueWallet)",
        "qr.descriptor": "Descriptor · {fingerprint}",
        "check.title": "Compare with your iPhone",
        "check.first_address": "First receive address",
        "check.fingerprint": "Fingerprint (descriptor only)",
        "check.zpub_note": "With zpub, check the address.",
        "check.help": "◀ back to the QR · Press: finish",
        "end.title": "Switch the device off",
        "end.body": "The seed is erased when the power is removed.",
        "end.paper": "Keep the paper with the rolls as safe as the phrase, or destroy it.",
        "sim.title": "Cold wallet · simulator",
        "sim.banner": "SIMULATOR · TESTING ONLY · DO NOT USE WITH REAL FUNDS",
        "shots.band": "TEST SEED — DO NOT USE",
    },
    "pt": {
        "error.title": "Algo deu errado",
        "error.body": "Desligue o aparelho e comece de novo.",
        "network.title": "Há uma conexão de rede",
        "network.body": (
            "Uma carteira fria não pode ter rede. Desconecte o adaptador, "
            "desligue e ligue de novo."
        ),
        "reset.title": "Começar de novo?",
        "reset.body": "Tudo o que você fez será apagado.",
        "reset.no": "Não",
        "reset.yes": "Sim, apagar",
        "help.choose_accept": "◀ ▶ escolher · Aperte: OK",
        "key2.start_over": "KEY2: começar de novo",
        "welcome.title": "Carteira fria",
        "welcome.offline": "Sem rede.",
        "welcome.stores_nothing": "Não guarda nada.",
        "welcome.how_many": "Quantas palavras?",
        "welcome.help": "◀ ▶ escolher · Aperte: começar",
        "rolls.of_total": "de {total}",
        "rolls.for": "Jogadas para",
        "rolls.words": "{words} palavras",
        "rolls.help": "Aperte: incluir · KEY3: apagar a última",
        "review.title": "Jogadas {first} a {last}",
        "review.editing": "Mudando a {n} · KEY3: desfazer",
        "review.compare": "Compare-as com seu papel",
        "review.help_editing": "▲ ▼ mudar · Aperte: salvar",
        "review.help": "Aperte: mudar · KEY1: tudo certo, seguir",
        "confirm.question": "Você comparou as {total} jogadas com seu papel?",
        "confirm.body": (
            "As jogadas são a sua frase. Guarde esse papel tão bem quanto a frase "
            "ou destrua-o ao terminar."
        ),
        "confirm.yes": "Sim, seguir",
        "confirm.no": "Não, revisar",
        "bad.title": "Estas jogadas não parecem aleatórias",
        "bad.face_share": "Uma face sai em mais de 30% das jogadas.",
        "bad.long_run": "Há jogadas iguais demais seguidas.",
        "bad.body": (
            "Jogue o dado de verdade para cada número. Corrija as jogadas ou "
            "comece de novo com KEY2."
        ),
        "bad.help": "Aperte: voltar às jogadas",
        "warning.title": "Que ninguém veja a tela",
        "warning.body": (
            "Pegue papel e lápis. Você vai ver {n} palavras. "
            "Depois vou pedir cada uma; responda olhando o papel."
        ),
        "warning.help": "Aperte: ver as palavras",
        "phrase.title": "Palavras {first} a {last} de {total}",
        "phrase.copy": "Copie estas palavras no papel",
        "phrase.fix": "Corrija seu papel",
        "phrase.review": "Revise seu papel",
        "phrase.help_fix": "◀ ▶ páginas · Aperte: voltar à prova",
        "phrase.help_review": "◀ ▶ páginas · Aperte: terminar a revisão",
        "phrase.help_next": "◀ voltar · ▶ ou Aperte: próximas",
        "phrase.help_last": "◀ voltar · Aperte: ir para a prova",
        "exam.title": "Prova: {n} de {total}",
        "exam.question": "Olhe seu papel. Qual é a {position}ª?",
        "exam.not_on_paper": "KEY3: não está no meu papel",
        "exam.help": "▲ ▼ escolher · Aperte: responder",
        "fail.title": "Revise a palavra {position}",
        "fail.body": "Olhe essa palavra na tela e corrija seu papel. Depois continue a prova.",
        "fail.help": "Aperte: ver a palavra",
        "passed.title": "Passou na prova",
        "passed.match": "Seu papel confere.",
        "passed.note": "Se seguir para o QR, a frase é apagada e você não poderá mais vê-la.",
        "passed.review": "Revisar as palavras",
        "passed.continue": "Seguir para o QR",
        "passed.help": "▲ ▼ escolher · Aperte: OK",
        "deriving.title": "Calculando a chave pública…",
        "deriving.body": "É calculada duas vezes, de duas formas diferentes. Aguarde alguns segundos.",
        "mismatch.title": "Os cálculos não coincidem",
        "mismatch.body": "Não use esta carteira nem este aparelho. Não envie dinheiro. Desligue-o.",
        "qr.zpub": "zpub (BlueWallet)",
        "qr.descriptor": "Descritor · {fingerprint}",
        "check.title": "Compare com seu iPhone",
        "check.first_address": "1º endereço de recebimento",
        "check.fingerprint": "Fingerprint, se usou o descritor",
        "check.zpub_note": "Com zpub, compare o endereço.",
        "check.help": "◀ voltar ao QR · Aperte: terminar",
        "end.title": "Desligue o aparelho",
        "end.body": "A semente é apagada quando a energia é cortada.",
        "end.paper": "Guarde o papel das jogadas como a frase, ou destrua-o.",
        "sim.title": "Carteira fria · simulador",
        "sim.banner": "SIMULADOR · SÓ PARA TESTES · NÃO USE COM DINHEIRO",
        "shots.band": "SEMENTE DE TESTE — NÃO USE",
    },
}

# Los dos avisos de core.rolls_quality_problem() vienen en español del núcleo,
# que no se toca. Aquí se traducen por su texto exacto; si el núcleo cambia
# uno, las pruebas lo detectan y, mientras tanto, se enseña tal cual.
CORE_ROLLS_PROBLEMS = {
    "Una cara sale en más del 30 % de las tiradas.": "bad.face_share",
    "Hay demasiadas tiradas iguales seguidas.": "bad.long_run",
}


def check_language(lang: str) -> str:
    """Devuelve el idioma si existe; si no, lanza ValueError."""
    if lang not in STRINGS:
        raise ValueError("Idioma desconocido. Usa en, es o pt.")
    return lang


def normalise_language(value: str) -> str | None:
    """Lee lo que se escribe en --lang: «EN», «pt-BR», «pt_br», «br», «es-MX»…

    Devuelve en, es o pt, o None si no reconoce el idioma. «br» y cualquier
    variante de pt van al portugués de Brasil, que es el único portugués que hay.
    """
    tag = value.strip().lower().replace("_", "-")
    if tag == "br":
        return "pt"
    base = tag.split("-", 1)[0]
    return base if base in STRINGS else None


def t(key: str, lang: str = DEFAULT_LANGUAGE, **values: object) -> str:
    """Texto de la clave en el idioma pedido, con los huecos rellenados."""
    text = STRINGS[check_language(lang)][key]
    return text.format(**values) if values else text


def placeholders(text: str) -> set[str]:
    """Nombres de los huecos {…} de un texto (para las pruebas)."""
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def rolls_problem(message: str, lang: str = DEFAULT_LANGUAGE) -> str:
    """Traduce el aviso de tiradas raras del núcleo; si no lo conoce, lo deja igual."""
    key = CORE_ROLLS_PROBLEMS.get(message)
    return t(key, lang) if key else message
