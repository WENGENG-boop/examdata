"""Apply visually verified local corrections to 0413/2026/Jun/11 only."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "indexes/0413/2026-Jun-11/cie-index.json"
BACKUP = ROOT / "work/0413-index-before-visual-repair.json"

TEXT = {
    "1": "Identify three types of sponsorship that a performer may receive. [3]",
    "2": "The diagram shows a human skeleton with joints labelled A, B and C. (a) Identify each of the following types of synovial joint: the joint labelled A; the joint labelled C. [2] (b) Compare the range of movement and stability of the joint labelled A with the joint labelled B. [2] (c) Describe a different function of three named structures/components of a synovial joint. [6] [Total: 10]",
    "2(a)": "Identify each of the following types of synovial joint: the joint labelled A; the joint labelled C. [2]",
    "2(b)": "Compare the range of movement and stability of the joint labelled A with the joint labelled B. [2]",
    "2(c)": "Describe a different function of three named structures/components of a synovial joint. [6]",
    "3": "Using three different examples from a named physical activity, explain how technology has supported improvements in performance. Provide the physical activity, three examples and an explanation for each. [6]",
    "4": "The photograph shows a performer playing badminton. (a) Complete the table to describe how each component of fitness benefits a badminton performer and identify a recognised fitness test for each component: agility, power and flexibility. [6] (b) A badminton player will require coordination when hitting the shuttlecock. Describe how to carry out the Anderson Wall Toss Coordination Test. [3] (c) A coach may use the results from fitness testing to plan a training programme. Other than fitness test scores, suggest three factors that could inform the design of a training programme. [3] [Total: 12]",
    "4(a)": "Complete the table to describe how each component of fitness benefits a badminton performer and identify a recognised fitness test for each component: agility, power and flexibility. [6]",
    "4(b)": "A badminton player will require coordination when hitting the shuttlecock. Describe how to carry out the Anderson Wall Toss Coordination Test. [3]",
    "4(c)": "A coach may use the results from fitness testing to plan a training programme. Other than fitness test scores, suggest three factors that could inform the design of a training programme. [3]",
    "5": "(a) Describe stroke volume. (b) Calculate the cardiac output of a person with a heart rate of 60 beats per minute and a stroke volume of 80 millilitres. Your answer should include an appropriate unit. [2] [Total: 3]",
    "5(a)": "Describe stroke volume. [1]",
    "5(b)": "Calculate the cardiac output of a person with a heart rate of 60 beats per minute and a stroke volume of 80 millilitres. Your answer should include an appropriate unit. [2]",
    "6": "The table shows three physical activities and a different method of training used by performers in each activity. (a) For each physical activity, explain a different benefit to performance of using the stated method of training. The activities and methods are: netball — circuit training; cricket — weight training; table tennis — high-intensity interval training (HIIT). [3] (b) The diagram shows a sports development pyramid. (i) Identify the levels of the sports development pyramid labelled A, B and C. [3] (ii) Describe three characteristics of the participation level of the sports development pyramid. [3] [Total: 9]",
    "6(a)": "For each physical activity, explain a different benefit to performance of using the stated method of training: netball — circuit training; cricket — weight training; table tennis — high-intensity interval training (HIIT). [3]",
    "6(b)": "The diagram shows a sports development pyramid. (i) Identify the levels of the pyramid labelled A, B and C. [3] (ii) Describe three characteristics of the participation level of the sports development pyramid. [3] [Total: 9]",
    "6(b)(i)": "Identify the levels of the sports development pyramid labelled A, B and C. [3]",
    "6(b)(ii)": "Describe three characteristics of the participation level of the sports development pyramid. [3]",
    "7": "Describe how each of the following factors can affect participation in physical activity: media coverage, family, education and discrimination. [4]",
    "8": "(a) Complete the graph by drawing the Yerkes-Dodson Law. Label both axes. [3] (b) The photograph shows performers in a rugby union match. Using different examples from a rugby union match, suggest when a performer needs each of the following levels of arousal to perform well, and justify each example: low level of arousal; high level of arousal. [4] [Total: 7]",
    "8(a)": "Complete the graph by drawing the Yerkes-Dodson Law. Label both axes. [3]",
    "8(b)": "The photograph shows performers in a rugby union match. Using different examples from a rugby union match, suggest when a performer needs a low level and a high level of arousal to perform well. Justify each example. [4]",
    "9": "The diagram shows part of the upper body and arm. (a) Identify the muscle labelled A and the muscle labelled B. [2] (b) Identify the muscle labelled C and describe its role when flexion occurs at the elbow. [3] (c) Fast-twitch muscle fibres and slow-twitch muscle fibres contract at different speeds. Compare two other features of fast-twitch and slow-twitch muscle fibres. [2] [Total: 7]",
    "9(a)": "Identify the muscle labelled A and the muscle labelled B. [2]",
    "9(b)": "Identify the muscle labelled C and describe its role when flexion occurs at the elbow. [3]",
    "9(c)": "Fast-twitch muscle fibres and slow-twitch muscle fibres contract at different speeds. Compare two other features of fast-twitch and slow-twitch muscle fibres. [2]",
    "10": "The diagrams A and B show stages of a basketball player shooting the ball. Identify the movement that occurs at joints X, Y and Z from diagram A to diagram B. [3]",
    "11": "(a) (i) Describe a function of each of the following structures of the heart: left atrium; right ventricle. [2] (ii) Complete the table to identify the components of blood and describe each component's function. The rows include red blood cells, white blood cells, platelets and plasma. [4] (b) (i) Describe two structural differences between arteries and veins. [2] (ii) Capillary walls are one cell thick, which allows gaseous exchange to take place. Describe two areas in the body where gaseous exchange takes place. [2] [Total: 10]",
    "11(a)": "(i) Describe a function of each of the following structures of the heart: left atrium; right ventricle. [2] (ii) Complete the table to identify the components of blood and describe each component's function. The rows include red blood cells, white blood cells, platelets and plasma. [4]",
    "11(a)(i)": "Describe a function of each of the following structures of the heart: left atrium; right ventricle. [2]",
    "11(a)(ii)": "Complete the table to identify the components of blood and describe each component's function. The rows include red blood cells, white blood cells, platelets and plasma. [4]",
    "11(b)": "(i) Describe two structural differences between arteries and veins. [2] (ii) Capillary walls are one cell thick, which allows gaseous exchange to take place. Describe two areas in the body where gaseous exchange takes place. [2] [Total: 10]",
    "11(b)(i)": "Describe two structural differences between arteries and veins. [2]",
    "11(b)(ii)": "Capillary walls are one cell thick, which allows gaseous exchange to take place. Describe two areas in the body where gaseous exchange takes place. [2]",
    "12": "(a) Describe three advantages and three disadvantages for a performer receiving visual guidance from a coach. [6] (b) Identify an appropriate type of feedback that may be used by a performer at the autonomous stage of learning. Justify your choice. [2] (c) The diagram shows a basic information processing model with stages A, B and C labelled. (i) Identify the stages labelled A, B and C. [3] (ii) Describe one difference between short-term memory and long-term memory. [1] [Total: 12]",
    "12(a)": "Describe three advantages and three disadvantages for a performer receiving visual guidance from a coach. [6]",
    "12(b)": "Identify an appropriate type of feedback that may be used by a performer at the autonomous stage of learning. Justify your choice. [2]",
    "12(c)": "The diagram shows a basic information processing model with stages A, B and C labelled. (i) Identify the stages labelled A, B and C. [3] (ii) Describe one difference between short-term memory and long-term memory. [1]",
    "12(c)(i)": "Identify the stages of the diagram labelled A, B and C. [3]",
    "12(c)(ii)": "Describe one difference between short-term memory and long-term memory. [1]",
    "13": "Complete the table by identifying the components of health and well-being described in each statement: ability to mix with other people; all body systems work well; feeling good; able to carry out everyday tasks. [4]",
    "14": "The photograph shows performers during a cross-country race. (a) Describe three possible disadvantages for a cross-country performer from taking performance-enhancing drugs (PED). [3] (b) Describe a different effect of two named PEDs for a cross-country performer. [4] (c) Describe the role of sports organising bodies in preventing and reducing the use of PEDs. [3] [Total: 10]",
    "14(a)": "Describe three possible disadvantages for a cross-country performer from taking performance-enhancing drugs (PED). [3]",
    "14(b)": "Describe a different effect of two named PEDs for a cross-country performer. [4]",
    "14(c)": "Describe the role of sports organising bodies in preventing and reducing the use of PEDs. [3]",
}

MARKS = {
    "1": 3, "2(a)": 2, "2(b)": 2, "2(c)": 6, "3": 6,
    "4(a)": 6, "4(b)": 3, "4(c)": 3,
    "5(a)": 1, "5(b)": 2,
    "6(a)": 3, "6(b)(i)": 3, "6(b)(ii)": 3,
    "7": 4, "8(a)": 3, "8(b)": 4,
    "9(a)": 2, "9(b)": 3, "9(c)": 2, "10": 3,
    "11(a)(i)": 2, "11(a)(ii)": 4, "11(b)(i)": 2, "11(b)(ii)": 2,
    "12(a)": 6, "12(b)": 2, "12(c)(i)": 3, "12(c)(ii)": 1,
    "13": 4, "14(a)": 3, "14(b)": 4, "14(c)": 3,
}

MS = {
    "1": [(7, [102.0, 63.6, 218.0, 729.2])],
    "2": [(7, [218.0, 63.6, 326.4, 729.2]), (8, [58.4, 66.0, 342.0, 729.2])],
    "2(a)": [(7, [218.0, 63.6, 276.8, 729.2])],
    "2(b)": [(7, [276.8, 63.6, 326.4, 729.2])],
    "2(c)": [(8, [102.0, 66.0, 342.0, 729.2])],
    "3": [(9, [102.0, 63.6, 472.4, 729.2])],
    "4": [(10, [102.0, 68.0, 445.2, 729.2]), (11, [58.4, 65.2, 337.2, 729.2])],
    "4(a)": [(10, [102.0, 68.0, 336.4, 729.2])],
    "4(b)": [(10, [336.4, 68.0, 445.2, 729.2])],
    "4(c)": [(11, [102.0, 65.2, 337.2, 729.2])],
    "5": [(11, [337.2, 65.2, 554.0, 729.2])],
    "5(a)": [(11, [337.2, 65.2, 407.6, 729.2])],
    "5(b)": [(11, [407.6, 65.2, 554.0, 729.2])],
    "6": [(12, [102.0, 61.6, 482.0, 729.2]), (13, [58.4, 121.2, 258.8, 729.2])],
    "6(a)": [(12, [102.0, 61.6, 422.4, 729.2])],
    "6(b)": [(12, [422.4, 61.6, 482.0, 729.2]), (13, [58.4, 121.2, 258.8, 729.2])],
    "6(b)(i)": [(12, [422.4, 61.6, 482.0, 729.2])],
    "6(b)(ii)": [(13, [102.0, 121.2, 258.8, 729.2])],
    "7": [(14, [102.0, 65.6, 365.6, 729.2])],
    "8": [(15, [102.0, 76.4, 296.8, 729.2]), (16, [58.4, 65.2, 532.0, 729.2])],
    "8(a)": [(15, [102.0, 76.4, 296.8, 729.2])],
    "8(b)": [(16, [102.0, 65.2, 532.0, 729.2])],
    "9": [(17, [102.0, 65.6, 490.4, 729.2])],
    "9(a)": [(17, [102.0, 65.6, 160.4, 729.2])],
    "9(b)": [(17, [160.4, 65.6, 266.8, 729.2])],
    "9(c)": [(17, [266.8, 65.6, 490.4, 729.2])],
    "10": [(18, [95.0, 84.8, 166.5, 735.2])],
    "11": [(18, [200.0, 84.8, 476.0, 735.2]), (19, [96.0, 68.8, 309.0, 729.2])],
    "11(a)": [(18, [200.0, 84.8, 476.0, 735.2])],
    "11(a)(i)": [(18, [200.0, 84.8, 318.5, 735.2])],
    "11(a)(ii)": [(18, [318.5, 84.8, 476.0, 735.2])],
    "11(b)": [(19, [96.0, 68.8, 309.0, 729.2])],
    "11(b)(i)": [(19, [96.0, 68.8, 250.5, 729.2])],
    "11(b)(ii)": [(19, [250.5, 68.8, 309.0, 729.2])],
    "12": [(20, [102.0, 121.2, 389.6, 729.2]), (21, [102.0, 64.8, 507.2, 729.2]), (22, [96.0, 70.0, 333.0, 729.2])],
    "12(a)": [(20, [102.0, 121.2, 389.6, 729.2])],
    "12(b)": [(21, [102.0, 64.8, 507.2, 729.2])],
    "12(c)": [(22, [96.0, 70.0, 333.0, 729.2])],
    "12(c)(i)": [(22, [96.0, 70.0, 166.5, 729.2])],
    "12(c)(ii)": [(22, [166.5, 70.0, 333.0, 729.2])],
    "13": [(22, [333.0, 70.0, 517.0, 729.2])],
    "14": [(23, [102.0, 70.4, 258.8, 729.2]), (24, [102.0, 96.8, 482.8, 729.2]), (25, [96.0, 121.2, 238.0, 729.2])],
    "14(a)": [(23, [102.0, 70.4, 258.8, 729.2])],
    "14(b)": [(24, [102.0, 96.8, 482.8, 729.2])],
    "14(c)": [(25, [96.0, 121.2, 238.0, 729.2])],
}


QP_FIX = [("6", 7), ("6(b)", 7), ("6(b)(ii)", 7), ("8", 9), ("8(b)", 9)]


def main() -> None:
    if not BACKUP.exists():
        shutil.copy2(INDEX, BACKUP)
    data = json.loads(INDEX.read_text(encoding="utf-8"))
    nodes = {str(item["question"]): item for item in data["questions"]}
    if set(nodes) != set(TEXT) or len(nodes) != 45:
        raise SystemExit(f"unexpected node keys: {len(nodes)} nodes")
    if set(MS) != set(TEXT):
        raise SystemExit("MS mapping does not cover all question nodes")
    for key, node in nodes.items():
        node["text"] = TEXT[key]
        node["marks"] = MARKS.get(key)
        node["ms"] = [{"page": p, "bbox": bbox} for p, bbox in MS[key]]
        node["uncertain"] = False
        node["notes"] = "Prompt and region visually checked against preserved local source page images."
    fixed = 0
    for key, page in QP_FIX:
        hits = [
            r
            for r in nodes[key]["qp"]
            if r["page"] == page
            and r["bbox"][0] == 92.4
            and r["bbox"][2] == 541.2
            and r["bbox"][3] == 748.4
        ]
        if len(hits) != 1:
            raise SystemExit(f"QP footer fix expected exactly 1 region for {key} p{page}, found {len(hits)}")
        hits[0]["bbox"][0] = 70.4
        fixed += 1
    if fixed != 5:
        raise SystemExit(f"QP footer fix applied {fixed} regions, expected 5")
    tmp = INDEX.with_name(INDEX.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, INDEX)
    print(f"updated {len(nodes)} question nodes; {sum(len(n['ms']) for n in nodes.values())} MS regions; {fixed} QP footer regions widened")


if __name__ == "__main__":
    main()
