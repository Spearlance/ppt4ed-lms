<template>
	<div
		v-if="remainingLessons.length > 0"
		data-testid="lessons-remaining-panel"
		class="rounded-md border border-outline-gray-2 bg-surface-gray-1 p-4"
	>
		<div class="flex items-center mb-3">
			<ListChecks class="size-5 stroke-1.5 text-ink-gray-7 mr-2" />
			<div class="text-sm font-semibold text-ink-gray-9">
				{{
					__('{0} lesson(s) remaining to complete this course').format(
						remainingLessons.length
					)
				}}
			</div>
		</div>
		<ul class="space-y-1.5 pl-1">
			<li
				v-for="lesson in remainingLessons"
				:key="lesson.name"
				class="text-sm flex items-start"
			>
				<span class="text-ink-gray-5 mr-2 shrink-0">{{ lesson.number }}</span>
				<router-link
					v-if="!lesson.is_locked"
					:to="{
						name: 'Lesson',
						params: {
							courseName: courseName,
							chapterNumber: lesson.chapterIdx,
							lessonNumber: lesson.lessonIdx,
						},
					}"
					class="text-ink-gray-8 hover:text-ink-gray-9 hover:underline"
				>
					{{ lesson.chapterTitle }} — {{ lesson.title }}
				</router-link>
				<span
					v-else
					class="text-ink-gray-5 inline-flex items-center"
					:title="__('Complete earlier chapters to unlock')"
				>
					<Lock class="size-3.5 stroke-1.5 mr-1 shrink-0" />
					{{ lesson.chapterTitle }} — {{ lesson.title }}
				</span>
			</li>
		</ul>
	</div>
</template>

<script setup>
import { computed } from 'vue'
import { createResource } from 'frappe-ui'
import { ListChecks, Lock } from 'lucide-vue-next'

const props = defineProps({
	courseName: {
		type: String,
		required: true,
	},
})

const outline = createResource({
	url: 'lms.lms.utils.get_course_outline',
	cache: ['course_outline', props.courseName],
	makeParams() {
		return {
			course: props.courseName,
			progress: true,
		}
	},
	auto: true,
})

const remainingLessons = computed(() => {
	if (!outline.data) return []
	const out = []
	for (const chapter of outline.data) {
		for (const lesson of chapter.lessons) {
			if (lesson.is_complete) continue
			const [chapterIdx, lessonIdx] = (lesson.number || '0-0').split('-')
			out.push({
				name: lesson.name,
				title: lesson.title,
				number: lesson.number,
				chapterTitle: chapter.title,
				chapterIdx,
				lessonIdx,
				is_locked: lesson.is_locked,
			})
		}
	}
	return out
})
</script>
