<template>
	<div class="p-5">
		<div class="flex justify-between w-full space-x-5">
			<div class="md:w-2/3">
				<div
					v-if="resource.data.resource_type"
					class="inline-block text-xs font-semibold uppercase tracking-wide bg-surface-gray-2 text-ink-gray-7 px-2 py-0.5 rounded-md mb-3"
				>
					{{ resource.data.resource_type }}
				</div>
				<div class="text-3xl font-semibold text-ink-gray-9">
					{{ resource.data.title }}
				</div>
				<div
					v-if="resource.data.short_introduction"
					class="my-3 leading-6 text-ink-gray-7"
				>
					{{ resource.data.short_introduction }}
				</div>
				<div
					v-if="resource.data.instructors?.length"
					class="flex items-center"
				>
					<span
						class="h-6 mr-1"
						:class="{
							'avatar-group overlap':
								resource.data.instructors.length > 1,
						}"
					>
						<UserAvatar
							v-for="instructor in resource.data.instructors"
							:key="instructor.name"
							:user="instructor"
						/>
					</span>
					<CourseInstructors :instructors="resource.data.instructors" />
				</div>
				<div v-if="resource.data.tags" class="flex my-4 w-fit">
					<Badge
						v-for="tag in resource.data.tags.split(', ')"
						:key="tag"
						theme="gray"
						size="lg"
						class="mr-2 text-ink-gray-9"
					>
						{{ tag }}
					</Badge>
				</div>

				<div class="md:hidden my-4">
					<ResourceCardOverlay :resource="resource" />
				</div>

				<div
					v-if="resource.data.description"
					v-html="resource.data.description"
					class="ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none !whitespace-normal mt-10"
				></div>

				<div v-if="resource.data.membership" class="mt-10">
					<div
						v-if="
							resource.data.is_single_lesson &&
							resource.data.single_lesson
						"
					>
						<div
							class="ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none !whitespace-normal"
						>
							<div
								v-if="resource.data.single_lesson.content"
								id="resource-editor"
							></div>
							<LessonContent
								v-else-if="resource.data.single_lesson.body"
								:content="resource.data.single_lesson.body"
								:youtube="resource.data.single_lesson.youtube"
								:quizId="resource.data.single_lesson.quiz_id"
							/>
						</div>
					</div>
					<CourseOutline
						v-else
						:title="__('Resource Contents')"
						:courseName="resource.data.name"
						:showOutline="true"
						:getProgress="true"
					/>
				</div>
			</div>

			<div class="hidden md:block">
				<ResourceCardOverlay :resource="resource" />
			</div>
		</div>
	</div>
</template>
<script setup>
import { Badge } from 'frappe-ui'
import { nextTick, watch } from 'vue'
import CourseOutline from '@/components/CourseOutline.vue'
import LessonContent from '@/components/LessonContent.vue'
import UserAvatar from '@/components/UserAvatar.vue'
import CourseInstructors from '@/components/CourseInstructors.vue'
import ResourceCardOverlay from '@/components/ResourceCardOverlay.vue'
import { enablePlyr } from '@/utils'

const props = defineProps({
	resource: {
		type: Object,
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
		if (
			data?.membership &&
			data?.is_single_lesson &&
			data?.single_lesson?.content
		) {
			nextTick(() => {
				renderEditor(data.single_lesson.content)
			})
		}
	},
	{ immediate: true }
)
</script>
<style scoped>
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
