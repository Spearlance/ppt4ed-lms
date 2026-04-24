import frappe


SURVEY_QUIZ_TITLE = "Course Survey"
COMPLETION_CHAPTER_TITLE = "Course Completion"
SURVEY_LESSON_TITLE = "Course Survey"
BODY_PLACEHOLDER = "​"  # zero-width space — Lesson.vue requires a truthy body


def execute():
	quiz_name = _ensure_survey_quiz()
	certified_courses = frappe.get_all(
		"LMS Course",
		filters={"enable_certification": 1},
		pluck="name",
	)
	for course_name in certified_courses:
		_ensure_feedback_lesson_on_course(course_name, quiz_name)
	frappe.db.commit()


def _ensure_survey_quiz():
	"""Return the name of the shared Course Survey quiz, creating or
	backfilling as needed so it runs in survey mode."""
	existing = frappe.db.get_value("LMS Quiz", {"title": SURVEY_QUIZ_TITLE}, "name")
	if existing:
		quiz = frappe.get_doc("LMS Quiz", existing)
		changed = False
		if not quiz.is_survey:
			quiz.is_survey = 1
			changed = True
		if quiz.passing_percentage:
			quiz.passing_percentage = 0
			changed = True
		if quiz.show_answers:
			quiz.show_answers = 0
			changed = True
		if changed:
			quiz.save(ignore_permissions=True)
		return existing
	return _create_survey_quiz()


def _create_survey_quiz():
	quiz = frappe.new_doc("LMS Quiz")
	quiz.title = SURVEY_QUIZ_TITLE
	quiz.passing_percentage = 0
	quiz.max_attempts = 0
	quiz.show_answers = 0
	quiz.shuffle_questions = 0
	quiz.is_survey = 1
	for q_data in _standard_questions():
		q_name = _create_question(q_data)
		quiz.append("questions", {"question": q_name, "marks": 1})
	quiz.insert(ignore_permissions=True)
	return quiz.name


def _standard_questions():
	return [
		{
			"question": "Therapy Discipline",
			"type": "Choices",
			"options": [
				("PT/PTA", True),  # first option flagged correct so LMS Question validation passes;
				("OT/OTA", False),  # correctness is ignored in survey mode (process_results bypass)
				("SLP/SLPA", False),
				("Other", False),
			],
		},
		{
			"question": "State, Discipline and professional license or certification number (e.g., FL PT 00000)",
			"type": "Open Ended",
		},
		{"question": "What did you like most about the course?", "type": "Open Ended"},
		{
			"question": "Was the information conveyed effectively and in a way you understood? If not, how can we improve?",
			"type": "Open Ended",
		},
		{
			"question": "Did the course meet your expectations? If not, how can we improve?",
			"type": "Open Ended",
		},
		{
			"question": "Share 1 takeaway that you hope to put into practice after this course.",
			"type": "Open Ended",
		},
		{"question": "How did you hear about this course?", "type": "Open Ended"},
		{"question": "Please share ideas for future course topics.", "type": "Open Ended"},
	]


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


def _ensure_feedback_lesson_on_course(course_name, quiz_name):
	course = frappe.get_doc("LMS Course", course_name)
	if _course_has_quiz_lesson(course, quiz_name):
		return

	chapter = frappe.new_doc("Course Chapter")
	chapter.course = course_name
	chapter.title = COMPLETION_CHAPTER_TITLE
	chapter.insert(ignore_permissions=True)

	lesson = frappe.new_doc("Course Lesson")
	lesson.course = course_name
	lesson.chapter = chapter.name
	lesson.title = SURVEY_LESSON_TITLE
	lesson.quiz_id = quiz_name
	lesson.body = BODY_PLACEHOLDER
	lesson.insert(ignore_permissions=True)

	chapter.append("lessons", {"lesson": lesson.name})
	chapter.save(ignore_permissions=True)

	course.append("chapters", {"chapter": chapter.name})
	course.save(ignore_permissions=True)


def _course_has_quiz_lesson(course, quiz_name):
	for ch_ref in course.chapters:
		lesson_quiz_ids = frappe.get_all(
			"Course Lesson",
			filters={"chapter": ch_ref.chapter, "quiz_id": quiz_name},
			pluck="name",
		)
		if lesson_quiz_ids:
			return True
	return False
