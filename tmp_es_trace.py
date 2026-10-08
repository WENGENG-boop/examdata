"""Trace Q8 reformulation sentences back to their source question in the same paper."""
import sqlite3
import sys

PAPERS = {
    2124: ["pone a disposición", "hagan visible", "una motivación para seguir", "se le dará mal",
           "agraciado", "traficantes", "varias horas de viaje", "bajar de los coches", "1800", "pateras"],
    2125: ["El edificio donde vivía", "huevos contra", "programa de estudios", "lo construye el propio",
           "aprender a buscar", "durante toda su vida", "tienden a colaborar", "está demostrado",
           "final de mes", "todavía es intenso"],
    2126: ["Sin necesidad de llevar", "seguidores le han convertido", "llevo 4 años",
           "potencial se esconde", "solamente queda esperar", "más difícil ser escuchado"],
    2129: ["Casi todos los niños", "haberla abandonado", "se licenció"],
    2131: ["se ven obligados", "nuestros modismos", "mucho talento"],
    2133: ["Al avanzar en edad", "aún más poder"],
    2136: ["anudaban la corbata", "evoluciona sin olvidar", "plataformas flotantes", "fondo del lago",
           "islas artificiales", "dentro de la moda", "películas de Almodóvar", "probar suerte en París",
           "se lo dije a mi familia", "cierta distancia"],
    2137: ["alquilan su cuerpo", "sigue teniendo asignada", "rol de cuidadora", "gran bondad",
           "María de la Onza", "quién era María", "cualquier español", "me siento tan ajeno", "San Valentín"],
    2139: ["España rural", "nueva tecnología", "hallazgo asombroso", "por muy ofensiva", "se den casos",
           "defender sus razones", "se le impuso", "crítica satírica"],
    2142: ["mapas precisos", "se reduce al 15", "boquiabierto", "llevar muchos años en España",
           "cuarto de siglo", "sin hacerse daño"],
    2145: ["después de escuchar música", "vuestros oídos", "hace cinco siglos", "conquistadores",
           "Museo del Prado", "Toda ignorancia"],
    2147: ["tecleando", "tomar notas en tu portátil", "espejismos", "cualquier hotel"],
    2148: ["cambie mis hábitos", "permitírsela", "en menos tiempo"],
}


def main():
    con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
    con.row_factory = sqlite3.Row
    for pid, phrases in PAPERS.items():
        rows = con.execute(
            'SELECT id, number_path, parent_id, stem_text FROM question WHERE paper_id=? ORDER BY id',
            (pid,)).fetchall()
        tags = {}
        for r in con.execute(
                '''SELECT qt.question_id, tn.code FROM question_taxonomy qt
                   JOIN taxonomy_node tn ON tn.id=qt.node_id
                   WHERE qt.question_id IN (SELECT id FROM question WHERE paper_id=?)''', (pid,)):
            tags.setdefault(r['question_id'], []).append(r['code'])
        print(f'######## paper {pid} ########')
        for ph in phrases:
            hits = []
            for r in rows:
                t = r['stem_text'] or ''
                i = t.find(ph)
                if i >= 0:
                    snippet = t[max(0, i - 70):i + 140].replace('\n', ' ')
                    hits.append(f"  {r['id']}[{r['number_path']}] tags={tags.get(r['id'], [])}: ...{snippet}...")
            print(f'### {ph!r}')
            if hits:
                print('\n'.join(hits))
            else:
                print('  NOT FOUND')
        print()


if __name__ == '__main__':
    main()
