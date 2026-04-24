<template>
	<!-- Single-lesson resource — show content directly -->
	<div
		v-if="resource.data?.is_single_lesson && resource.data?.single_lesson"
		class="max-w-4xl mx-auto p-5 pt-10"
	>
		<div
			v-if="resource.data.resource_type"
			class="inline-block text-xs font-semibold bg-surface-gray-2 px-2 py-0.5 rounded-md mb-3"
		>
			{{ resource.data.resource_type }}
		</div>
		<h1 class="text-3xl font-semibold text-ink-gray-9 mb-2">
			{{ resource.data.title }}
		</h1>
		<div class="flex items-center mb-6">
			<span
				class="h-6 mr-1"
				:class="{ 'avatar-group overlap': resource.data.instructors?.length > 1 }"
			>
				<UserAvatar
					v-for="instructor in resource.data.instructors"
					:user="instructor"
				/>
			</span>
			<CourseInstructors
				v-if="resource.data.instructors"
				:instructors="resource.data.instructors"
			/>
		</div>

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
	<div v-else class="max-w-4xl mx-auto p-5 pt-10">
		<div
			v-if="resource.data?.resource_type"
			class="inline-block text-xs font-semibold bg-surface-gray-2 px-2 py-0.5 rounded-md mb-3"
		>
			{{ resource.data.resource_type }}
		</div>
		<h1 class="text-3xl font-semibold text-ink-gray-9 mb-2">
			{{ resource.data?.title }}
		</h1>
		<div class="flex items-center mb-4">
			<span
				class="h-6 mr-1"
				:class="{ 'avatar-group overlap': resource.data?.instructors?.length > 1 }"
			>
				<UserAvatar
					v-for="instructor in resource.data?.instructors"
					:user="instructor"
				/>
			</span>
			<CourseInstructors
				v-if="resource.data?.instructors"
				:instructors="resource.data.instructors"
			/>
		</div>
		<p v-if="resource.data?.short_introduction" class="text-ink-gray-7 mb-6">
			{{ resource.data.short_introduction }}
		</p>

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
import UserAvatar from '@/components/UserAvatar.vue'
import CourseInstructors from '@/components/CourseInstructors.vue'
import CourseOutline from '@/components/CourseOutline.vue'
import LessonContent from '@/components/LessonContent.vue'

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
<style>
.avatar-group {
	display: inline-flex;
	align-items: center;
}

.avatar-group .avatar {
	transition: margin 0.1s ease-in-out;
}

.avatar-group.overlap .avatar + .avatar {
	margin-left: calc(-8px);
}
</style>
