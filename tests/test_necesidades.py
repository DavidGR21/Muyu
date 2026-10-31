from server.brain.instincts import SENALES, Necesidades


def test_hambre_energia_y_compania_bajan_con_su_tiempo():
    n = Necesidades()
    antes = (n.saciedad, n.energia, n.compania)
    n.pasar(4, despierta=True)
    assert n.saciedad < antes[0] and n.energia < antes[1] and n.compania < antes[2]


def test_dormida_se_recupera_y_el_hambre_avanza_mas_lento():
    despierta, dormida = Necesidades(energia=0.3), Necesidades(energia=0.3)
    despierta.pasar(4, despierta=True)
    dormida.pasar(4, despierta=False)
    assert dormida.energia > 0.3 > despierta.energia
    assert dormida.saciedad > despierta.saciedad


def test_alimentar_llena_la_saciedad():
    n = Necesidades(saciedad=0.2)
    n.recibir(SENALES["alimentar"])
    assert n.saciedad > 0.5


def test_la_seguridad_cae_con_los_sustos_y_vuelve_sola_mas_rapido_si_esta_protegida():
    expuesta, escondida = Necesidades(), Necesidades()
    for n in (expuesta, escondida):
        n.recibir(SENALES["regañar"])
        n.asustar(0.8)
    assert expuesta.seguridad < 0.6
    expuesta.pasar(0.25, despierta=True)
    escondida.pasar(0.25, despierta=True, protegida=1.0)
    assert escondida.seguridad > expuesta.seguridad


def test_el_aburrimiento_crece_sin_estimulo_y_baja_jugando():
    n = Necesidades()
    n.aburrirse(200)
    assert n.aburrimiento > 0.7
    n.recibir(SENALES["jugar"])
    assert n.aburrimiento < 0.5


def test_las_necesidades_insatisfechas_bajan_la_linea_base_emocional():
    bien = Necesidades().efecto_emocional()
    mal = Necesidades(saciedad=0.05, compania=0.05, seguridad=0.1).efecto_emocional()
    assert mal[0] < bien[0] - 0.5      # menos placer
    assert mal[2] < bien[2]            # menos dominancia (insegura)
