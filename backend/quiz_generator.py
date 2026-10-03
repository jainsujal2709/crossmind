import re
import random
from collections import Counter
import nlp

def generate_quiz_questions(segs, topic="General Study Material", difficulty="medium", count=15, q_types=None):
    if not q_types:
        q_types = ["mcq", "true_false", "msq"]
    
    concepts_list = nlp.concepts(segs, top=80)
    concept_terms = [c["term"] for c in concepts_list]
    all_sentences = list(nlp.sentences(segs))
    
    questions = []
    used_sentences = set()
    q_id = 1
    
    # Process concepts to generate questions
    for concept_obj in concepts_list:
        term = concept_obj["term"]
        matching_sents = [s for s in all_sentences if re.search(rf"\b{term}\b", s[0], re.I) and s[0] not in used_sentences]
        if not matching_sents:
            continue
            
        matching_sents.sort(key=lambda s: abs(len(s[0]) - 100))
        sent, src = matching_sents[0]
        used_sentences.add(sent)
        
        # Decide question type based on available types
        chosen_type = random.choice(q_types)
        
        if chosen_type == "true_false":
            # Generate True/False
            is_true = random.choice([True, False])
            if is_true:
                q_text = f"True or False: {sent}"
                correct_ans = "True"
                exp = f"This statement is directly supported by the source notes: '{sent}'"
            else:
                # Mutate sent by replacing term with another distractor concept
                distractors = [c for c in concept_terms if c.upper() != term.upper()]
                alt_term = random.choice(distractors) if distractors else "incorrect concept"
                mutated_sent = re.sub(rf"\b{term}\b", alt_term, sent, flags=re.I)
                q_text = f"True or False: {mutated_sent}"
                correct_ans = "False"
                exp = f"False. The correct concept is '{term}', as stated in the notes: '{sent}'"
                
            questions.append({
                "id": q_id,
                "type": "true_false",
                "question": q_text,
                "options": ["True", "False"],
                "answer": correct_ans,
                "hint": f"Focus on the definition or concept related to {term if is_true else 'the statement'}.",
                "explanation": exp,
                "source": src
            })
            q_id += 1

        elif chosen_type == "msq":
            # Multiple Select: Pick term and ask which statements/terms apply
            masked = nlp._mask(sent, term)
            other_terms = [c for c in concept_terms if c.upper() != term.upper()]
            distractor_pool = random.sample(other_terms, min(3, len(other_terms))) if len(other_terms) >= 3 else ["Data", "System", "Process"]
            
            correct_options = [term.capitalize(), f"Concept described as: {sent[:40]}..."]
            incorrect_options = [d.capitalize() for d in distractor_pool[:2]]
            
            all_opts = list(set(correct_options + incorrect_options))
            random.shuffle(all_opts)
            
            questions.append({
                "id": q_id,
                "type": "msq",
                "question": f"Which of the following terms or statements relate to: '{masked}'?",
                "options": all_opts,
                "answer": [opt for opt in all_opts if opt in correct_options],
                "hint": f"Select all options that correctly match the context of {term}.",
                "explanation": f"The key concept is '{term}'. Context: '{sent}'",
                "source": src
            })
            q_id += 1

        else:  # MCQ
            masked = nlp._mask(sent, term)
            other_terms = [c for c in concept_terms if c.upper() != term.upper()]
            distractor_pool = random.sample(other_terms, min(3, len(other_terms))) if len(other_terms) >= 3 else ["Algorithm", "Database", "Framework"]
            
            options = [term.capitalize()] + [d.capitalize() for d in distractor_pool[:3]]
            # Deduplicate while preserving order
            unique_options = []
            for opt in options:
                if opt.upper() not in [u.upper() for u in unique_options]:
                    unique_options.append(opt)
            while len(unique_options) < 4:
                unique_options.append(f"Option {len(unique_options)+1}")
            
            random.shuffle(unique_options)
            
            questions.append({
                "id": q_id,
                "type": "mcq",
                "question": f"Fill in the blank: {masked}",
                "options": unique_options,
                "answer": term.capitalize(),
                "hint": f"The answer starts with '{term[0].upper()}' and has {len(term)} letters.",
                "explanation": f"The correct term is '{term}'. Source context: '{sent}'",
                "source": src
            })
            q_id += 1
            
        if len(questions) >= count:
            break

    # If we need more questions to reach requested count, generate fallback MCQs from sentences
    while len(questions) < count and len(all_sentences) > len(used_sentences):
        sent, src = [s for s in all_sentences if s[0] not in used_sentences][0]
        used_sentences.add(sent)
        words = [w for w in re.findall(r"[A-Za-z]{5,12}", sent) if w.lower() not in nlp.STOP]
        if not words:
            continue
        word = words[0]
        masked = nlp._mask(sent, word)
        
        opts = [word.capitalize(), "Structure", "Method", "Protocol"]
        random.shuffle(opts)
        
        questions.append({
            "id": q_id,
            "type": "mcq",
            "question": f"Complete the statement: {masked}",
            "options": opts,
            "answer": word.capitalize(),
            "hint": f"Look closely at sentence context.",
            "explanation": f"Source excerpt: '{sent}'",
            "source": src
        })
        q_id += 1

    return questions[:count]
