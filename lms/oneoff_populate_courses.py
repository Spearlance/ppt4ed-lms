"""
One-off migration: populate lessons/chapters/quizzes for 5 PPT4Ed courses.

Wipes existing chapters/lessons/quizzes on the 5 target courses, then rebuilds
from inline data. Run with:

    docker exec lms-backend-1 bench --site devlms.ppt4ed.org execute lms.oneoff_populate_courses.run

Dry-run mode rolls back at the end:

    docker exec lms-backend-1 bench --site devlms.ppt4ed.org execute lms.oneoff_populate_courses.run --kwargs '{"dry_run": true}'
"""

import frappe


CATCH_THE_WAVE = "catch-the-wave-introduction-to-whole-body-vibration-in-pediatric-therapy-for-pts-ots-and-slps"
POWER_OF_PLAY = "the-power-of-play-linking-play-to-language-cognitive-social-emotional-literacy-development"
ONE_STEP_AHEAD = "one-step-ahead-introduction-to-pediatric-lower-extremity-orthotics"
UPPER_EXTREMITY = "introduction-to-upper-extremity-splinting-for-function-in-pediatrics"
RETRAIN_THERAPIST = "retrain-the-therapist-brain-a-neurodiversity-affirming-approach-to-pediatric-therapy"

ALL_COURSES = [CATCH_THE_WAVE, POWER_OF_PLAY, ONE_STEP_AHEAD, UPPER_EXTREMITY, RETRAIN_THERAPIST]

SHORT_NAMES = {
    CATCH_THE_WAVE: "Catch the Wave",
    POWER_OF_PLAY: "Power of Play",
    ONE_STEP_AHEAD: "One Step Ahead",
    UPPER_EXTREMITY: "Upper Extremity",
    RETRAIN_THERAPIST: "Retrain the Therapist Brain",
}

SURVEY_QUIZ_TITLE = "Course Survey"


# ------------------------------------------------------------------
# Question helpers
# ------------------------------------------------------------------

def tf(text, is_true):
    """True/false as a 2-option Choices question."""
    return {
        "question": text,
        "type": "Choices",
        "options": [("TRUE", is_true), ("FALSE", not is_true)],
    }


def mc(text, options, correct_idx):
    """Multiple choice. `options` is a list of strings. `correct_idx` is 0-based."""
    return {
        "question": text,
        "type": "Choices",
        "options": [(opt, i == correct_idx) for i, opt in enumerate(options)],
    }


def mc_all(text, options):
    """Multiple choice where the source question had 'All of the above' as the
    correct answer. We drop the 'All of the above' option and mark all remaining
    as correct (multi-select). Caps at 4 options."""
    return {
        "question": text,
        "type": "Choices",
        "options": [(opt, True) for opt in options[:4]],
    }


def open_ended(text):
    return {"question": text, "type": "Open Ended", "options": None}


def short_text(text):
    return {"question": text, "type": "Short Text", "options": None}


# ------------------------------------------------------------------
# Course data
# ------------------------------------------------------------------

CATCH_THE_WAVE_DATA = {
    "course": CATCH_THE_WAVE,
    "chapters": [
        {
            "title": "Lecture Part 1",
            "video": "https://youtu.be/VEc6PkMnvdM",
            "quiz": [
                tf("Children may have difficulty tolerating side-alternating mechano-stimulation at times due to active gastro-esophageal reflux, sinus congestion, headaches or acute infections.", True),
                tf("Standing on the Galileo at 20 hz creates less G-force than walking or getting up from a chair.", True),
            ],
        },
        {
            "title": "Lecture Part 2",
            "video": "https://youtu.be/RSwuFm-zPas",
            "quiz": [
                tf("Motor learning is enhanced using the Galileo when children participate in meaningful, intentional activity.", True),
                tf("Allowing children explore the Galileo with their hands before standing on it helps them adjust to the powerful but usually intriguing and pleasant experience of vibration.", True),
            ],
        },
        {
            "title": "Lab 1",
            "video": "https://youtu.be/7e-yUAGrsKM",
            "quiz": [
                tf("The Wobble Function creates slight changes in frequency to help keep the nervous system 'alert' and prevent accommodation.", True),
                tf("Children with orthopedic implants should never use the Galileo.", False),
            ],
        },
        {
            "title": "Lab 2",
            "video": "https://youtu.be/yFr6tPJySZE",
            "quiz": [
                tf("The lowest frequency is the easiest and therefore you should start low with most children when introducing side-alternating mechano-stimulation.", False),
                tf("Torticollis is a contraindication to using the Galileo.", False),
            ],
        },
        {
            "title": "Lab 3",
            "video": "https://youtu.be/1DoIFHvl-ic",
            "quiz": [
                tf("Increasing frequency to above 25 hz may help to increase grasp strength using the Mano Vibrating Dumbbell.", True),
                tf("Therapeutically assisting children sitting in wheelchairs to raise the Mano Vibrating Dumbbell above shoulder level can help improve sitting posture.", True),
            ],
        },
    ],
}


POWER_OF_PLAY_DATA = {
    "course": POWER_OF_PLAY,
    "chapters": [
        {
            "title": "Course Video",
            "video": "https://youtu.be/lmtt-m4jz5U",
            "quiz": [
                mc("Which term does not describe play in infancy?",
                   ["Prelinguistic", "Exploratory", "Sensorimotor", "Dramatic"], 3),
                tf("Babbling starts at 3 months of age.", False),
                tf("Symbolic Play and language are closely related.", True),
                tf("Joint attention is important to Presymbolic and Symbolic Play.", True),
                tf("Parents should discourage their baby from mouthing objects/toys.", False),
                tf("Play begins at 2 years of age.", False),
                tf("Object permanence facilitates cognitive, language, memory, emotional, and spatial skill development.", True),
                tf('An example of agent-action is "baby sleeping".', True),
                tf("Skills needed for academic success are built on play.", True),
                tf("Children are generally commenting and engaging in discourse with their dolls/figures/characters at 17 months of age.", False),
                tf("Joint attention is the ability to share focus of attention with another person on an object or event.", True),
                tf("Internal performance of play refers to the quality of a child's play.", True),
                tf("There are fewer conversational turns when children engage with their iPads or electronic toys.", True),
                tf("Some children with autism spectrum disorder engage in symbolic play as an expected behavior.", True),
            ],
        },
    ],
}


ONE_STEP_AHEAD_DATA = {
    "course": ONE_STEP_AHEAD,
    "chapters": [
        {
            "title": "Part 1",
            "video": "https://youtu.be/_8hfEHaYG2w",
            "quiz": [
                tf("Early movement patterns (typical or atypical) may continue to impact skeletal modeling throughout life.", True),
                tf("Once a child reaches adulthood, their bones do not continue to remodel.", False),
                tf("20-40% of all children born today may have torticollis and plagiocephaly.", True),
                tf("Greater than (>) 50 degree Cobb angle in patients with scoliosis will require surgical correction.", True),
                tf("A soft trunk orthosis for children with low muscle tone is contraindicated as it will result in continued weakness of core muscles.", False),
            ],
        },
        {
            "title": "Part 2",
            "video": "https://youtu.be/3YzNdg9szSk",
            "quiz": [
                tf("10% of all newborn babies have some hip instability.", True),
                tf("All babies are born with fairly straight femoral neck to shaft angle (also known as Coxa Valga).", True),
                tf("Creeping, cruising and walking too early causes hip dysplasia in children.", False),
                tf("Children who are not walking independently by the age of 3 years, should be placed in a stander with legs abducted approximately 30 degrees to help seat the femoral head better in the acetabulum.", True),
                tf("Hip helpers are recommended for children with hip dysplasia.", False),
            ],
        },
        {
            "title": "Part 3",
            "video": "https://youtu.be/iq55fVMkbaI",
            "quiz": [
                tf("20-60% of all children diagnosed with autism are 'toe walkers'.", True),
                tf("Calcaneal alignment should be assessed only in standing when considering orthotics.", False),
                tf("Babies who 'skip' creeping are advanced and usually begin walking faster than babies who creep.", False),
                tf("When evaluating for ankle foot orthoses, the only range of motion measurements needed are ankle dorsiflexion and plantarflexion.", False),
                tf("AFOs should never cause callouses or blisters.", True),
            ],
        },
        {
            "title": "Part 4",
            "video": "https://youtu.be/jnlXgmyK_wc",
            "quiz": [
                tf("Toe walking is mostly caused by spasticity.", False),
                tf("Toddlers who toe walk often have a history or torticollis, severe reflux, sensory sensitivities, or prematurity.", True),
                tf("Retained patterns of toe walking into elementary school ages and beyond may result in heel cord contractures.", True),
                tf("Articulated AFOs should always be prescribed for children with cerebral palsy to maintain ankle flexibility.", False),
                tf("AFOs should never be used with a heel wedge since all AFOs should be made at 90 degrees shaft to floor angle.", False),
            ],
        },
        {
            "title": "Part 5",
            "video": "https://youtu.be/7TtHVVbRVMw",
            "quiz": [
                tf("Casting for AFOs should always keep the ankle position at 90 degrees.", False),
                tf("A doctor's prescription or a letter of medical necessity is required for the orthotist to provide orthotics.", True),
                tf("Once a child begins wearing orthotics they will always need them.", False),
                tf("Custom orthoses that are deemed medically necessary are typically covered by insurance once per year for children.", True),
                tf("Orthotics usually need a period of weaning to improve tolerance.", True),
            ],
        },
        {
            "title": "Part 6",
            "video": "https://youtu.be/O-TiOFxvp44",
            "quiz": [],
        },
    ],
}


UPPER_EXTREMITY_DATA = {
    "course": UPPER_EXTREMITY,
    "chapters": [
        {
            "title": "Part 1",
            "video": "https://youtu.be/jZwE_7TYQyg",
            "quiz": [
                tf("Assessment when considering an orthotic for a child includes: P/AROM, Strength, Palmar creases, Position of hand at rest and during functional task, Muscle tone, Sensory systems, Patient/caregiver interview.", True),
                tf("It is best to apply a splint carefully to avoid direct pressure over the growth plate area.", True),
                tf("When applying an upper extremity splint to a pediatric patient, it is important to avoid blocking joints where movement for function is needed.", True),
                mc("When choosing a splint for a pediatric patient, what are important goals to consider?",
                   ["Improvement in alignment or ROM",
                    "Prevention or correction of deformities",
                    "Muscle tone Management",
                    "All of the above"], 3),
                tf("Before choosing a splint, the therapist should complete a comprehensive assessment of Upper Extremity and Hand Function.", True),
            ],
        },
        {
            "title": "Part 2",
            "video": "https://youtu.be/zJrOqoELEZ4",
            "quiz": [
                tf("The purpose of a resting hand splint is to allow movement with support during functional tasks.", False),
                tf("Mobilization Splints, or splints designed to move or mobilize primary and secondary joints, include Serial Splinting, Static Progressive Splinting, and Dynamic Splints.", True),
                mc("What is an advantage to using Thermoplastic Splinting Materials?",
                   ["Stronger Material", "Bulky, heavier", "Limits hand function", "Limits Sensory feedback"], 0),
                tf("An Advantage of a thermoplastic stay is that you can easily remove from the splint based on the activity.", False),
                tf("Supination/Pronation strap provides constant low level stretch to forearm muscles and helps to promote bilateral use of upper extremities.", True),
            ],
        },
        {
            "title": "Part 3",
            "video": "https://youtu.be/TNPuhXFbT4Q",
            "quiz": [
                tf("Assessing trunk and body posture is irrelevant when assessing for an upper extremity orthotic.", False),
                mc("What does poor trunk alignment/support affect?",
                   ["Head position", "Vision Development", "Fine Motor Skills", "All of the Above"], 3),
                tf("If you provide a splint, you do not need to do any further treatment as part of your treatment plan.", False),
                tf("Trunk supports allow children to put less effort into posture, and focus more on other skills.", True),
                tf("When assessing for orthotics, therapists should complete a whole body assessment- not just upper extremities.", True),
            ],
        },
        {
            "title": "Part 4",
            "video": "https://youtu.be/OzowHKcv9dA",
            "quiz": [
                tf("Extreme wrist flexion or extension positions can inhibit hand functions and should be considered when molding and fitting a splint.", True),
                tf("When applying a splint to a child, it is important to allow the child to touch, feel, and be part of the process.", True),
                tf("Aluminum stays are adjusted by bending to desired position, and may be easily repositioned based on child's needs.", True),
                tf("It is ok to splint a hand in a flat position.", False),
                tf("Palmar creases should be used as a guide when splinting and may be left free or immobilized based on splinting goals.", True),
            ],
        },
        {
            "title": "Part 5",
            "video": "https://youtu.be/2y10LjsSEF4",
            "quiz": [
                mc("Which of the following are vital aspects of patient/caregiver education when a child receives an orthotic?",
                   ["Wear schedule",
                    "Instructions on donning/doffing",
                    "Orthotic care instructions",
                    "All of the above"], 3),
                tf("Grip Strength changes with wrist position changes.", True),
                tf("Wider straps help with force displacement and reduces risk for irritation or redness.", True),
                tf("When adding padding to distribute/remove pressure, you should add the pad directly on top of pressure area.", False),
                tf("With new splints, it is important to gradually increase wear time, and check for fit, pressure points, and circulation routinely.", True),
            ],
        },
        {
            "title": "Part 6",
            "video": "https://youtu.be/oMAW89l4YNY",
            "quiz": [
                tf("It is important to provide caregiver education on the expected outcome and purpose of splints in order to increase compliance with wear.", True),
                mc_all("When providing donning instructions to the caregiver, what should the therapist do? (Select all that apply.)",
                       ["Show the caregiver in person how to apply splint.",
                        "Observe the caregiver applying splint during the session.",
                        "Have caregiver take pictures or video for reference later.",
                        "Request the caregiver to don orthotic before arriving at next session in order to observe accuracy in application."]),
                tf("Therapist should label orthotics and stays to indicate orientation and placement.", True),
                tf("The child should be involved in choosing color, pattern, or decorations for splint to promote compliance.", True),
                mc_all("Team members involved in evaluating and providing orthotics include: (Select all that apply.)",
                       ["The caregiver and child.",
                        "The orthotist.",
                        "The treating therapist.",
                        "The Orthopedic and/or primary physician."]),
            ],
        },
    ],
    "bonus_chapter": {
        "title": "Bonus Content",
        "videos": [
            ("Apply Thermoplastic to Neoprene", "https://youtu.be/Ix3y7gFuhwI"),
            ("Heating Benik's Thermoplastic Supports", "https://youtu.be/OW4qpXNeu6k"),
            ("Pedi Wrap Elbow Immobilizer Donning Tutorial", "https://youtube.com/shorts/DIThR345R48"),
            ("Articulated Elbow Orthosis Donning Tutorial", "https://youtu.be/21R5PQkKQIs"),
            ("Choosing UE Orthotics Tutorial", "https://youtu.be/IVN9PXViDxg"),
            ("Removable Volar Pan Extension Hand Splint Donning Tutorial", "https://youtube.com/shorts/P04mmOm1afE"),
            ("Rotation Strap Donning Tutorial", "https://youtu.be/2WPz06exn9g"),
            ("Wrist Hand Orthosis Donning Tutorial", "https://youtu.be/wDnFQ9ja_nc"),
        ],
        "has_bonus_pdf": True,
    },
}


RETRAIN_THERAPIST_DATA = {
    "course": RETRAIN_THERAPIST,
    "chapters": [
        {
            "title": "Part 1",
            "video": "https://youtu.be/rEsIROqvcd0",
            "quiz": [
                tf("In 2013, the Diagnostic and Statistical Manual of Mental Disorders (DSM-5) made a classification change to recognize only 'Autism Spectrum Disorder', and no longer recognized other diagnoses such as Asperger's Syndrome.", True),
                mc("How does the bio-medical model view disability?",
                   ["It views disability as a challenge based on the barriers of society.",
                    "It views disability as 'deficit based/pathological', with goal to move towards 'normal'.",
                    "It views disability from a strengths based approach."], 1),
                mc("What is the basic definition of 'Neurodivergent'?",
                   ["Having the style of neurocognitive functioning that falls within the dominant social standards of 'Normal'.",
                    "Having neurocognitive functioning considered 'typical' within a population.",
                    "Having a mind that functions in ways that diverge significantly from the dominant societal standards of 'Normal'."], 2),
                mc("In recent years there has been a push to use terminology that is regarded as neuro-affirming. Which of these terms is considered Neuro-affirming?",
                   ["Asperger's Syndrome", "Autistic", "Low Functioning Autism", "High Functioning Autism"], 1),
                mc_all("What is the impact of using terms that are not neuro-affirming? (Select all that apply.)",
                       ["Erases Individual variations in ability.",
                        "May restrict access to support for those deemed 'high functioning'.",
                        "Denies autonomy and agency to those deemed 'low functioning'.",
                        "May lower expectations and limit opportunities for success."]),
            ],
        },
        {
            "title": "Part 2",
            "video": "https://youtu.be/iKrCDLvmHmc",
            "quiz": [
                mc("What are the four main functions of behavior?",
                   ["Biological, emotional, social, cognitive",
                    "Escape or avoidance, attention, tangibles, sensory/automatic",
                    "Primary, secondary, positive, negative",
                    "Instinctive, learned, motivated, goal-oriented"], 1),
                tf("Negative attention is letting the child know we like something they did.", False),
                mc("A child throws a tantrum in a store when their parent refuses to buy them a toy. This behavior is most likely driven by:",
                   ["Sensory stimulation needs.",
                    "Escape from an unwanted situation.",
                    "Desire for attention from their parent.",
                    "Accessing the desired toy."], 3),
                tf("Plugging your ears, rocking back and forth are examples of automatic functions.", True),
                tf("The Circumstances View promotes a compassionate approach to additional reasons that behavior may be occurring.", True),
                mc("How does the PEOP model differ from a purely biomedical approach to occupational therapy?",
                   ["It focuses on diagnoses and medical interventions.",
                    "It considers the social and environmental factors impacting performance.",
                    "It prioritizes physical rehabilitation exercises.",
                    "It is not client-centered."], 1),
                mc("What are the four main patterns of sensory processing?",
                   ["Hyperactive, hypoactive, introverted, extroverted",
                    "Visual, auditory, tactile, olfactory",
                    "Low registration, sensation seeking, sensory sensitive, sensation avoiding",
                    "Analytical, creative, logical, emotional"], 2),
                mc("Which of the following is NOT an example of sensory avoiding behavior?",
                   ["A child who only eats bland foods and avoids anything with strong textures.",
                    "An adult who wears noise-canceling headphones in crowded places.",
                    "A toddler who dislikes bright lights and prefers dimmed environments.",
                    "An athlete who enjoys vigorous activity and seeks out physical stimulation."], 3),
                mc("Which child is most likely exhibiting sensory seeking behavior?",
                   ["Sarah, who prefers quiet reading and calming activities.",
                    "Ethan, who enjoys jumping on furniture and climbing high places.",
                    "Olivia, who dislikes strong textures and avoids wearing certain clothes.",
                    "Liam, who finds bright lights and loud noises overwhelming."], 1),
                mc("Which component of the PEOP model focuses on a client's strengths, weaknesses, and limitations?",
                   ["Environment", "Occupation", "Person", "Performance"], 2),
            ],
        },
        {
            "title": "Part 3",
            "video": "https://youtu.be/In1kZTc_WmI",
            "quiz": [
                mc("What is the core principle of a strengths-based approach in working with individuals?",
                   ["Identify and address weaknesses to prevent future problems.",
                    "Diagnose and treat underlying mental health conditions.",
                    "Focus on building upon existing strengths and skills.",
                    "Develop interventions based on past failures and limitations."], 2),
                mc("When working with a client who exhibits echolalia in a speech or occupational therapy session, how can a therapist best utilize a strengths-based approach?",
                   ["Focus on eliminating echolalia completely through intensive repetition activities.",
                    "Use clear and direct commands, avoiding questions that might trigger echolalia.",
                    "Identify the underlying function of echolalia and leverage it to promote communication and engagement.",
                    "Ignore echolalia and solely focus on completing therapy tasks without verbal interaction."], 2),
                mc("What is the primary goal when addressing concerns about stimming in a classroom setting?",
                   ["To eliminate all stimming behaviors completely.",
                    "To find ways to reduce stimming that is disruptive to others.",
                    "To educate and create an inclusive environment where all behaviors are respected.",
                    "To enforce strict rules and consequences for any stimming that occurs."], 2),
                mc("Which tools or strategies are MOST helpful in creating a predictable environment for children within the classroom, home and community?",
                   ["Strict schedules and rigid routines with minimal flexibility.",
                    "Visual schedules with picture cues, timers, and clear expectations.",
                    "Sensory deprivation techniques to avoid potential distractions.",
                    "Unstructured playtime without established boundaries or limitations."], 1),
                tf("It's not our job to teach the kids to mask their unique traits and simply comply.", True),
            ],
        },
        {
            "title": "Part 4",
            "video": "https://youtu.be/nHtp4dcVpgY",
            "quiz": [
                mc("What is the first step in goal writing?",
                   ["Choose most appropriate formal/informal assessment measures.",
                    "Gather all your information about the child (parent interview, concerns from parents and school/preschool, your observations).",
                    "Determine the child's strengths and areas of concerns.",
                    "Prioritize areas of concerns."], 1),
                mc("What does the 'R' in SMART goals stand for?",
                   ["Reasonable", "Relevant", "Realistic", "Rewarding"], 1),
                mc("Which of the following ARE the two main types of goals used in Applied Behavior Analysis (ABA)?",
                   ["Functional and Typography.",
                    "Behavioral and Emotional",
                    "Developmental and Social",
                    "Cognitive and Physical"], 0),
                mc("What is NOT an example of strength based terms to use in goal writing?",
                   ["Adult led/Child Led",
                    "Energetic, quickly moves from one toy to another",
                    "Low Functioning",
                    "Participate in shared, structured task"], 2),
                tf("Child will attend to a non-preferred task for 5 minutes in 4/5 opportunities uses neuro-affirming terminology.", False),
            ],
        },
        {
            "title": "Part 5",
            "video": "https://youtu.be/sm8KU6tLhUA",
            "assignment": "How do you plan to implement a Strengths Based approach with the clientele you work with?",
        },
    ],
}


ALL_COURSE_DATA = [
    CATCH_THE_WAVE_DATA,
    POWER_OF_PLAY_DATA,
    ONE_STEP_AHEAD_DATA,
    UPPER_EXTREMITY_DATA,
    RETRAIN_THERAPIST_DATA,
]


# ------------------------------------------------------------------
# Wipe phase
# ------------------------------------------------------------------

def _delete_quiz_with_questions(quiz_name):
    if not frappe.db.exists("LMS Quiz", quiz_name):
        return
    quiz = frappe.get_doc("LMS Quiz", quiz_name)
    question_names = [qq.question for qq in quiz.questions if qq.question]
    frappe.delete_doc("LMS Quiz", quiz_name, force=True, ignore_permissions=True)
    for qn in question_names:
        if frappe.db.exists("LMS Question", qn):
            try:
                frappe.delete_doc("LMS Question", qn, force=True, ignore_permissions=True)
            except Exception as e:
                print(f"  could not delete question {qn}: {e}")


def wipe_existing():
    print("Wiping existing content for target courses...")

    # 1. Walk chapters/lessons via the course's chapters child table first
    for course_slug in ALL_COURSES:
        if not frappe.db.exists("LMS Course", course_slug):
            print(f"  course not found: {course_slug} — skipping")
            continue
        course = frappe.get_doc("LMS Course", course_slug)
        for ch_ref in list(course.chapters):
            _wipe_chapter(ch_ref.chapter)
        course.chapters = []
        course.save(ignore_permissions=True)

    # 2. Catch any orphans (chapters linked to course but not in the table)
    for course_slug in ALL_COURSES:
        for ch_name in frappe.get_all("Course Chapter", filters={"course": course_slug}, pluck="name"):
            _wipe_chapter(ch_name)

    # 3. Any remaining quizzes linked to these courses
    for q_name in frappe.get_all("LMS Quiz", filters={"course": ["in", ALL_COURSES]}, pluck="name"):
        _delete_quiz_with_questions(q_name)

    # 4. Any prior Course Survey quiz(zes) — match on title because name may vary
    for q_name in frappe.get_all("LMS Quiz", filters={"title": SURVEY_QUIZ_TITLE}, pluck="name"):
        _delete_quiz_with_questions(q_name)


def _wipe_chapter(chapter_name):
    if not frappe.db.exists("Course Chapter", chapter_name):
        return
    chapter = frappe.get_doc("Course Chapter", chapter_name)
    for ls_ref in list(chapter.lessons):
        _wipe_lesson(ls_ref.lesson)
    # Also sweep any orphan lessons that weren't in the child table
    for ls_name in frappe.get_all("Course Lesson", filters={"chapter": chapter_name}, pluck="name"):
        _wipe_lesson(ls_name)
    frappe.delete_doc("Course Chapter", chapter_name, force=True, ignore_permissions=True)


def _wipe_lesson(lesson_name):
    if not frappe.db.exists("Course Lesson", lesson_name):
        return
    lesson = frappe.get_doc("Course Lesson", lesson_name)
    if lesson.quiz_id:
        _delete_quiz_with_questions(lesson.quiz_id)
    frappe.delete_doc("Course Lesson", lesson_name, force=True, ignore_permissions=True)


# ------------------------------------------------------------------
# Create phase
# ------------------------------------------------------------------

def _create_question(q_data):
    q = frappe.new_doc("LMS Question")
    q.question = q_data["question"]
    q.type = q_data["type"]
    if q_data["type"] == "Choices":
        options = q_data["options"][:4]
        for i, (opt, is_correct) in enumerate(options, 1):
            setattr(q, f"option_{i}", opt)
            setattr(q, f"is_correct_{i}", 1 if is_correct else 0)
        num_correct = sum(1 for _, c in options if c)
        q.multiple = 1 if num_correct > 1 else 0
    q.insert(ignore_permissions=True)
    return q.name


def _create_quiz(title, questions_data, passing_percentage=80, is_survey=False):
    quiz = frappe.new_doc("LMS Quiz")
    quiz.title = title
    quiz.passing_percentage = passing_percentage
    quiz.max_attempts = 0  # unlimited
    quiz.show_answers = 0 if is_survey else 1
    quiz.shuffle_questions = 0
    quiz.is_survey = 1 if is_survey else 0
    for q_data in questions_data:
        q_name = _create_question(q_data)
        quiz.append("questions", {"question": q_name, "marks": 1})
    quiz.insert(ignore_permissions=True)
    return quiz.name


def create_survey_quiz():
    print("Creating Course Survey quiz...")
    return _create_quiz(
        SURVEY_QUIZ_TITLE,
        [
            mc(
                "Therapy Discipline",
                ["PT/PTA", "OT/OTA", "SLP/SLPA", "Other"],
                correct_idx=0,  # ungraded in survey mode; value is ignored
            ),
            short_text("State, Discipline and professional license or certification number (e.g., FL PT 00000)"),
            open_ended("What did you like most about the course?"),
            open_ended("Was the information conveyed effectively and in a way you understood? If not, how can we improve?"),
            open_ended("Did the course meet your expectations? If not, how can we improve?"),
            open_ended("Share 1 takeaway that you hope to put into practice after this course."),
            open_ended("How did you hear about this course?"),
            open_ended("Please share ideas for future course topics."),
        ],
        passing_percentage=0,
        is_survey=True,
    )


def _new_lesson(course_slug, chapter_name, title):
    lesson = frappe.new_doc("Course Lesson")
    lesson.course = course_slug
    lesson.chapter = chapter_name
    lesson.title = title
    return lesson


# Lesson.vue only mounts LessonContent when body is truthy, so every lesson
# needs a non-empty body even if we're relying on the youtube/quiz_id fields.
_BODY_PLACEHOLDER = "​"  # zero-width space: truthy but renders invisibly


def _create_video_lesson(course_slug, chapter_name, title, video_url):
    lesson = _new_lesson(course_slug, chapter_name, title)
    lesson.youtube = video_url
    lesson.body = _BODY_PLACEHOLDER
    lesson.insert(ignore_permissions=True)
    return lesson.name


def _create_placeholder_lesson(course_slug, chapter_name, title):
    lesson = _new_lesson(course_slug, chapter_name, title)
    lesson.body = f"_{title} coming soon._"
    lesson.insert(ignore_permissions=True)
    return lesson.name


def _create_quiz_lesson(course_slug, chapter_name, title, quiz_name):
    lesson = _new_lesson(course_slug, chapter_name, title)
    lesson.quiz_id = quiz_name
    lesson.body = _BODY_PLACEHOLDER
    lesson.insert(ignore_permissions=True)
    return lesson.name


def _create_chapter(course_slug, title):
    chapter = frappe.new_doc("Course Chapter")
    chapter.course = course_slug
    chapter.title = title
    chapter.insert(ignore_permissions=True)
    return chapter


def populate_main_chapter(course_slug, chapter_data):
    """One chapter = Video + Resources + Slides + (Quiz or Assignment)."""
    chapter = _create_chapter(course_slug, chapter_data["title"])

    video = _create_video_lesson(course_slug, chapter.name, "Course Video", chapter_data["video"])
    chapter.append("lessons", {"lesson": video})

    resources = _create_placeholder_lesson(course_slug, chapter.name, "Resources")
    chapter.append("lessons", {"lesson": resources})

    slides = _create_placeholder_lesson(course_slug, chapter.name, "Course Slides")
    chapter.append("lessons", {"lesson": slides})

    if chapter_data.get("assignment"):
        # Lesson.vue doesn't render the Course Lesson `question` field inline,
        # so we model the open-ended prompt as a 1-question Open Ended quiz.
        quiz_title = f"{SHORT_NAMES[course_slug]} — {chapter_data['title']} Assignment"
        quiz_name = _create_quiz(
            quiz_title,
            [open_ended(chapter_data["assignment"])],
            passing_percentage=0,  # open-ended; any submission passes
        )
        quiz_lesson = _create_quiz_lesson(course_slug, chapter.name, "Assignment", quiz_name)
        chapter.append("lessons", {"lesson": quiz_lesson})
    elif chapter_data.get("quiz"):
        quiz_title = f"{SHORT_NAMES[course_slug]} — {chapter_data['title']} Quiz"
        quiz_name = _create_quiz(quiz_title, chapter_data["quiz"])
        quiz_lesson = _create_quiz_lesson(course_slug, chapter.name, "Quiz", quiz_name)
        chapter.append("lessons", {"lesson": quiz_lesson})

    chapter.save(ignore_permissions=True)
    return chapter.name


def populate_bonus_chapter(course_slug, bonus_data):
    chapter = _create_chapter(course_slug, bonus_data["title"])
    for title, url in bonus_data["videos"]:
        lesson = _create_video_lesson(course_slug, chapter.name, title, url)
        chapter.append("lessons", {"lesson": lesson})
    if bonus_data.get("has_bonus_pdf"):
        pdf_lesson = _create_placeholder_lesson(course_slug, chapter.name, "Bonus PDF")
        chapter.append("lessons", {"lesson": pdf_lesson})
    chapter.save(ignore_permissions=True)
    return chapter.name


def populate_completion_chapter(course_slug, survey_quiz_name):
    chapter = _create_chapter(course_slug, "Course Completion")
    lesson = _create_quiz_lesson(course_slug, chapter.name, "Course Survey", survey_quiz_name)
    chapter.append("lessons", {"lesson": lesson})
    chapter.save(ignore_permissions=True)
    return chapter.name


def populate_course(data, survey_quiz_name):
    course_slug = data["course"]
    print(f"Populating {SHORT_NAMES[course_slug]}...")

    chapter_names = []
    for chapter_data in data["chapters"]:
        chapter_names.append(populate_main_chapter(course_slug, chapter_data))

    if "bonus_chapter" in data:
        chapter_names.append(populate_bonus_chapter(course_slug, data["bonus_chapter"]))

    chapter_names.append(populate_completion_chapter(course_slug, survey_quiz_name))

    # Fetch course fresh after all the side-effects from chapter/lesson creation
    # (fetched course_title on Course Chapter bumps the parent Course's modified)
    course = frappe.get_doc("LMS Course", course_slug)
    for ch_name in chapter_names:
        course.append("chapters", {"chapter": ch_name})
    course.save(ignore_permissions=True)


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def run(dry_run=False):
    print(f"=== populate_courses run (dry_run={dry_run}) ===")
    try:
        wipe_existing()
        survey_quiz_name = create_survey_quiz()
        for data in ALL_COURSE_DATA:
            populate_course(data, survey_quiz_name)

        if dry_run:
            frappe.db.rollback()
            print("DRY RUN complete — rolled back.")
        else:
            frappe.db.commit()
            print("Done — committed.")
    except Exception:
        frappe.db.rollback()
        print("ERROR — rolled back.")
        raise
