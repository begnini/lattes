import requests
import os

import numpy as np


def load_csv(filename):
    """
    Carrega o csv com as informacoes dos curriculuns.

    Parameters
    ----------
    filename : str, nome do arquivo csv.

    Notes
    -----
    Esse arquivo eh obtido em http://memoria.cnpq.br/web/portal-lattes/extracoes-de-dados
    A ultima versao parece ser de 2017 e contem pouco mais de 5M de cvs.
    """
    reader = open(filename).readlines()

    rows = []
    for line in reader:
        line = line.strip()
        rows.append(line.split(';'))

    return rows


def construct_headers(cookie, id):
    """Constroi o cabecalho HTTP que sera enviado na requisicao.

    Parameters
    ----------
    cookie : str, string com o cookie a ser passado na requisicao
    id : str, string com o id do CV, usado no referer

    Notes
    -----
    Todas as requisicoes desse sistema enviam esses cabecalhos,
    apenas por padronizacao, nao foi testado quais sao realmente necessarios.
    """
    headers = {
        'Host': 'buscatextual.cnpq.br',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:63.0) Gecko/20100101 Firefox/63.0',
        'Accept-Language': 'pt-BR,en-US;q=0.7,en;q=0.3',
        'Referer': 'http://buscatextual.cnpq.br/buscatextual/download.do?idcnpq=%s' % (id),
        'DNT': '1',
        'Connection': 'keep-alive',
        'Cookie': cookie,
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache'
    }

    return headers


def first_cookie(id):
    """Obtem o primeiro cookie da sessao.

    Parameters
    ----------
    id : str, string com o id do CV a ser baixado

    Notes
    -----
    O cookie eh passado zerado, para obter uma nova sessao.
    """
    url = 'http://buscatextual.cnpq.br/buscatextual/download.do?idcnpq=%s' % (id)
    
    headers = construct_headers('', id)
    
    response = requests.get(url, headers=headers)
    cookies  = response.headers['Set-Cookie']
    
    return ";".join([c.split(';')[0].strip() for c in cookies.split(',')])



def save_zip(content, id):
    """Salva o zip gravado, conforme a estrutura de diretorio definida.

    Parameters
    ----------
    content : byte, arquivo zip na memoria
    id : str, id do CV baixado

    Notes
    -----
    Como sao 5 milhoes de zips, colocar tudo num diretorio unico pode ferrar
    com o filesystem, por isso foi criado 2 niveis de diretorio, onde o 
    primeiro nivel sao os 2 penultimos digitos do id, e ultimo nivel os 2
    ultimos digitos. Como exemplo, se tivermos um id '123456789', a estrutura
    ficaria do tipo:
        zip/
            67/
                89/
                    123456789.zip

    Com isso, conseguimos ter 100 diretorios no primeiro nivel e 100 no segundo
    nivel. Cada diretorio final deve ficar com cerca de 510 arquivos zip.
    """

    dir1 = id[-4:-2]
    dir2 = id[-2:]

    directory = os.path.join('zip', dir1, dir2)
    if not os.path.isdir(directory):
        os.makedirs(directory)

    filename = os.path.join(directory, '%s.zip' % (id))
    with open(filename, 'wb') as handler:
        handler.write(content)


def download(cookie, id):
    """Faz download do zip com o CV e salva no disco.

    Parameters
    ----------
    cookie : str, cookie com as informacoes da sessao
    id : str, id do CV

    Notes
    -----
    As informacoes devem ser enviadas como multipart/form-data, em vez de
    serem enviadas como informacoes do POST normal.
    """
    url = 'http://buscatextual.cnpq.br/buscatextual/download.do'

    payload = {
        'metodo': (None, 'captchaValido'),
        'idcnpq': (None, id),
        'informado': (None, ''),
    }

    headers = construct_headers(cookie, id)

    response = requests.post(url, files=payload, headers=headers)
    save_zip(response.content, id)


def save_captcha(content, id):
    """Salva a imagem do captcha, conforme a estrutura de diretorio definida.

    Parameters
    ----------
    content : byte, imagem do captcha na memoria
    id : str, id do CV a ser baixado

    Notes
    -----
    Como sao 5 milhoes de captchas, colocar tudo num diretorio unico pode 
    ferrar com o filesystem, por isso foi criado 2 niveis de diretorio, onde o 
    primeiro nivel sao os 2 penultimos digitos do id, e ultimo nivel os 2
    ultimos digitos. Como exemplo, se tivermos um id '123456789', a estrutura
    ficaria do tipo:
        captcha/
            67/
                89/
                    123456789.png

    Com isso, conseguimos ter 100 diretorios no primeiro nivel e 100 no segundo
    nivel. Cada diretorio final deve ficar com cerca de 510 arquivos png.

    O captcha eh necessario apenas durante a sessao, podendo ser apagado depois,
    ou, ser carregado direto da memoria para o opencv, tornando essa funcao
    obsoleta.
    """
    dir1 = id[-4:-2]
    dir2 = id[-2:]

    directory = os.path.join('captcha', dir1, dir2)
    if not os.path.isdir(directory):
        os.makedirs(directory)

    filename = os.path.join(directory, '%s.png' % (id))
    with open(filename, 'wb') as handler:
        handler.write(content)


def get_captcha(cookie, id):
    """Faz o download da imagem do captcha e salva no disco.

    Parameters
    ----------
    cookie : str, cookie com as informacoes da sessao
    id : str, id do CV

    Notes
    -----
    As vezes o captcha retorna um erro (NullPointerException) em html. Quando
    isso acontece, passar o arquivo html pro opencv explode tudo. Por isso,
    preferimos abortar a sessao quando o captcha nao puder ser gerado.

    As vezes, nessa requisicao, o cookie muda, adicionando novos cookies.
    Por isso retornamos o cookie novo, caso exista.
    """
    captcha_url = 'http://buscatextual.cnpq.br/buscatextual/servlet/captcha?metodo=getImagemCaptcha'

    headers  = construct_headers(cookie, id)
    response = requests.get(captcha_url, headers=headers)
    
    if response.content.find(b'<html>') > -1:
        return False

    save_captcha(response.content, id)
        
    if not 'Set-Cookie' in response.headers:
        return cookie

    cookies  = response.headers['Set-Cookie']
    return ";".join([c.split(';')[0].strip() for c in cookies.split(',')])



def post_captcha(captcha, cookie, id):
    """Envia o captcha reconhecido para permitir o download.

    Parameters
    ----------
    captcha : str, captcha reconhecido
    coookie : str, cookie com as informacoes da sessao
    id : str, id do CV

    Notes
    -----
    Esse endpoint retorna um json, com {'estado': 'erro'}, caso o captcha esteja errado
    ou {'estado': 'sucesso'}, caso o captcha esteja certo.
    """
    captcha_url = 'http://buscatextual.cnpq.br/buscatextual/servlet/captcha?informado=%s&metodo=validaCaptcha' % (captcha)
    
    headers  = construct_headers(cookie, id)
    response = requests.get(captcha_url, headers=headers)
    response = response.json()
    
    if response['estado'] == 'erro':
        return False
    
    return True


import cv2
import string
import keras
import tensorflow as tf

def load_model(modelname):
    """Carrega o modelo treinado para reconhecer os captchas.

    Parameters
    ----------
    modelname : str, nome do modelo keras gravado no disco

    Notes
    -----
    Retorna 2 informacoes, o modelo carregado e o grafo default.
    Esse grafo eh necessario quando for fazer apenas predicao com o modelo, 
    conforme https://github.com/keras-team/keras/issues/6462
    """
    model = keras.models.load_model(modelname)
    graph = tf.get_default_graph()

    return (model, graph)

def recognize(id, model):
    """Faz o reconhecimento do captcha.

    Parameters
    ----------
    id : str, id do CV, para referenciar a imagem do captcha baixado
    model : tuple (model, graph), modelo do keras para o reconhecimento

    Notes
    -----
    O modelo tem 4 outpus, cada com um 36 classes (maiusculos + digitos).
    Ele pega o mais provavel de cada output, transforma em char e retorna
    a string com os 4.
    """
    model, graph = model

    classes = sorted(list(string.ascii_uppercase) + list(string.digits))

    filename = os.path.join('captcha', id[-4:-2], id[-2:], '%s.png' % (id))
    
    image = cv2.imread(filename)
    image = image[:, :140, :]
    
    input_shape = image.shape
    
    with graph.as_default():
        predict     = model.predict([image.reshape(1, *input_shape)])
        predictions = [predict[i].argmax(axis=1)[0] for i in range(4)]
        
        return "".join(classes[p] for p in predictions)


def lattes(id, model):
    """Faz o download de um CV lattes.

    Parameters
    ----------
    id : str, id do CV a ser baixado
    model : tuple (model, graph), modelo do keras, a ser usado no reconhecimento do captcha

    Notes
    -----
    Controla o fluxo da sessao, necessario para baixar o zip.
    """
    filename = os.path.join('zip', id[-4:-2], id[-2:], '%s.zip' % (id))

    if os.path.isfile(filename):
        return True
    
    cookie = first_cookie(id)
    cookie = get_captcha(cookie, id)
    
    if cookie is False:
        return False
    
    captcha = recognize(id, model)
    s = post_captcha(captcha, cookie, id)
    
    if not s:
        return False
    
    download(cookie, id)
    return True


import tqdm

def main(ids, model, progress):
    """Faz o download de uma lista de CVs.

    Parameteres
    -----------
    ids : list, lista com os ids a serem baixados
    model : tuple (model, graph) modelo do keras, usado no reconhecimento do captcha
    progress : tqdm, progress bar
    """
    errors = 0

    for id in ids:
        result = lattes(id, model)
        if not result:
            errors = errors + 1

        progress.update(1) 
    
    return errors

def filter_downloaded(ids):
    """Filtra os ids ja baixados

    Parameters
    ----------
    ids : list, com todos os ids

    Notes
    -----
    Olha no disco se ja existe o zip do id, se existir, remove da lista de 
    ids que devem ser baixados.
    """
    not_downloaded = []

    for id in tqdm.tqdm(ids):
        filename = os.path.join('zip', id[-4:-2], id[-2:], '%s.zip' % (id))

        if not os.path.isfile(filename):
            not_downloaded.append(id)

    return not_downloaded


import asyncio
import concurrent.futures

async def dispatcher(ids, model):
    """Download asincrono dos CVs

    Parameteres
    -----------
    ids : list, lista com os ids a serem baixados
    model : tuple (model, graph) modelo do keras, usado no reconhecimento do captcha

    Notes
    -----
    Divide a lista de ids em conjuntos, esses conjuntos serao enviados a
    threads para serem baixados. O ideal seria um CV por thread, mas como
    cada task faz uma copia do modelo keras, isso explode a memoria.
    """
    MAX_THREADS = 100
    MAX_TASKS   = MAX_THREADS * 10

    sets = np.array_split(ids, MAX_TASKS)

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        loop = asyncio.get_event_loop()
        
        futures = []
    
        progress = tqdm.tqdm(ids)

        for set_id in sets:
            future = loop.run_in_executor(executor, main, set_id, model, progress)
            futures.append(future)
        
        for response in await asyncio.gather(*futures):
            pass


if __name__ == '__main__':
    

    rows = load_csv('lattes.csv')
    ids  = [row[0] for row in rows]
    ids  = filter_downloaded(ids)

    print ('Processing %d elements...\n' % (len(ids)))

    model = load_model('model.model')

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(dispatcher(ids, model))
    finally:
        loop.close()
    