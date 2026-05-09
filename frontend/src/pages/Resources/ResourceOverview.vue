<template>
	<!-- Single-lesson resource — show content directly -->
	<div
		v-if="resource.data?.is_single_lesson && resource.data?.single_lesson"
		class="max-w-4xl mx-auto"
	>
		<div
			class="ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none !whitespace-normal"
		>
			<div v-if="resource.data.single_lesson.content" id="resource-editor"></div>
			<LessonContent
				v-else-if="resource.data.single_lesson.body"
				:content="resource.data.single_lesson.body"
				:youtube="resource.data.single_lesson.youtube"
				:quizId="resource.data.single_lesson.quiz_id"
			/>
		</div>
	</div>

	<!-- Multi-lesson resource — show course outline -->
	<div v-else class="max-w-4xl mx-auto">
		<div v-if="resource.data?.membership" class="mb-6">
			<router-link
				v-if="resource.data.membership.current_lesson || resource.data.current_lesson"
				:to="{
					name: 'Lesson',
					params: {
						courseName: resourceName,
						chapterNumber: (resource.data.current_lesson || '1.1').split('.')[0],
						lessonNumber: (resource.data.current_lesson || '1.1').split('.')[1] || '1',
					},
				}"
			>
				<Button variant="solid">
					{{ resource.data.membership.progress > 0 ? __('Continue Learning') : __('Start Learning') }}
				</Button>
			</router-link>
		</div>

		<CourseOutline
			:courseName="resourceName"
			:getProgress="resource.data?.membership ? true : false"
		/>
	</div>
</template>
<script setup>
import { Button } from 'frappe-ui'
import { nextTick, watch } from 'vue'
import CourseOutline from '@/components/CourseOutline.vue'
import LessonContent from '@/components/LessonContent.vue'
import { enablePlyr } from '@/utils'

const props = defineProps({
	resource: {
		type: Object,
		required: true,
	},
	resourceName: {
		type: String,
		required: true,
	},
})

let editorInstance = null

const renderEditor = async (content) => {
	const holder = document.getElementById('resource-editor')
	if (!holder) return

	const { getEditorTools } = await import('@/utils')
	const { default: EditorJS } = await import('@editorjs/editorjs')

	holder.innerHTML = ''
	editorInstance = new EditorJS({
		holder: 'resource-editor',
		tools: getEditorTools(),
		data: JSON.parse(content),
		readOnly: true,
		defaultBlock: 'embed',
	})
	// EditorJS's `embed` block writes a `<div class="video-player">`
	// placeholder; Plyr hydrates those into the actual YouTube/Vimeo iframe.
	// Without this call the video area renders blank — same fix Lesson.vue
	// has been carrying since day one.
	await editorInstance.isReady
	await enablePlyr()
}

watch(
	() => props.resource.data,
	(data) => {
		if (data?.is_single_lesson && data?.single_lesson?.content) {
			nextTick(() => {
				renderEditor(data.single_lesson.content)
			})
		}
	},
	{ immediate: true }
)
</script>
