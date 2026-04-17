<template>
	<div v-if="resource.data">
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs class="h-7" :items="breadcrumbs" />
			<Button
				v-if="user.data?.is_moderator"
				@click="showEditModal = true"
			>
				<template #prefix>
					<Pencil class="h-4 w-4 stroke-1.5" />
				</template>
				{{ __('Edit') }}
			</Button>
		</header>

		<EditResourceModal
			v-if="resource.data"
			v-model="showEditModal"
			:resourceDoc="resource.data"
			@updated="resource.reload()"
		/>

		<!-- Guest: Teaser + Email Gate -->
		<div v-if="!user.data" class="max-w-3xl mx-auto p-5 pt-10">
			<div
				v-if="resource.data.image"
				class="w-full h-64 bg-cover bg-center bg-no-repeat rounded-lg mb-6"
				:style="{ backgroundImage: `url('${encodeURI(resource.data.image)}')` }"
			></div>
			<div
				v-if="resource.data.resource_type"
				class="inline-block text-xs font-semibold bg-surface-gray-2 px-2 py-0.5 rounded-md mb-3"
			>
				{{ resource.data.resource_type }}
			</div>
			<h1 class="text-3xl font-semibold text-ink-gray-9 mb-3">
				{{ resource.data.title }}
			</h1>
			<p class="text-ink-gray-7 mb-8 leading-relaxed">
				{{ resource.data.short_introduction }}
			</p>

			<!-- Email capture form -->
			<div class="bg-surface-gray-2 rounded-lg p-6">
				<div v-if="!emailSent" class="space-y-4">
					<div class="text-lg font-semibold text-ink-gray-9">
						{{ __('Get free access to this resource') }}
					</div>
					<p class="text-sm text-ink-gray-7">
						{{ __('Enter your email and we\'ll send you a link to access this resource.') }}
					</p>
					<div class="flex flex-col sm:flex-row gap-3">
						<FormControl
							v-model="email"
							type="email"
							:placeholder="__('Your email address')"
							class="flex-1"
							@keyup.enter="requestAccess()"
						/>
						<Button
							variant="solid"
							:loading="accessRequest.loading"
							@click="requestAccess()"
						>
							{{ __('Get Free Access') }}
						</Button>
					</div>
					<ErrorMessage :message="accessRequest.error" />
				</div>
				<div v-else class="text-center py-4">
					<div class="text-lg font-semibold text-ink-gray-9 mb-2">
						{{ __('Check your email!') }}
					</div>
					<p class="text-sm text-ink-gray-7">
						{{ __('We\'ve sent a link to {0}. Click it to access this resource.').replace('{0}', email) }}
					</p>
				</div>
			</div>
		</div>

		<!-- Logged in: Single-lesson resource — show content directly -->
		<div
			v-else-if="resource.data.is_single_lesson && resource.data.single_lesson"
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

			<!-- Render lesson content -->
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

		<!-- Logged in: Multi-lesson resource — show course outline -->
		<div v-else class="max-w-4xl mx-auto p-5 pt-10">
			<div
				v-if="resource.data.resource_type"
				class="inline-block text-xs font-semibold bg-surface-gray-2 px-2 py-0.5 rounded-md mb-3"
			>
				{{ resource.data.resource_type }}
			</div>
			<h1 class="text-3xl font-semibold text-ink-gray-9 mb-2">
				{{ resource.data.title }}
			</h1>
			<div class="flex items-center mb-4">
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
			<p v-if="resource.data.short_introduction" class="text-ink-gray-7 mb-6">
				{{ resource.data.short_introduction }}
			</p>

			<div v-if="resource.data.membership" class="mb-6">
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
				:getProgress="resource.data.membership ? true : false"
			/>
		</div>
	</div>
</template>
<script setup>
import {
	Breadcrumbs,
	Button,
	call,
	createResource,
	ErrorMessage,
	FormControl,
	usePageMeta,
} from 'frappe-ui'
import { computed, inject, ref, watch, nextTick } from 'vue'
import { Pencil } from 'lucide-vue-next'
import { sessionStore } from '@/stores/session'
import EditResourceModal from '@/pages/Resources/EditResourceModal.vue'
import UserAvatar from '@/components/UserAvatar.vue'
import CourseInstructors from '@/components/CourseInstructors.vue'
import CourseOutline from '@/components/CourseOutline.vue'
import LessonContent from '@/components/LessonContent.vue'

const user = inject('$user')
const { brand } = sessionStore()
const email = ref('')
const emailSent = ref(false)
const showEditModal = ref(false)

const props = defineProps({
	resourceName: {
		type: String,
		required: true,
	},
})

const resource = createResource({
	url: 'lms.lms.utils.get_resource_details',
	makeParams() {
		return { resource: props.resourceName }
	},
	auto: true,
})

const accessRequest = createResource({
	url: 'lms.lms.api.request_resource_access',
	makeParams() {
		return {
			email: email.value,
			resource_name: props.resourceName,
		}
	},
})

const requestAccess = () => {
	if (!email.value) return
	accessRequest.submit({}, {
		onSuccess() {
			emailSent.value = true
		},
	})
}

// Auto-enroll when resource loads and user is logged in
watch(
	() => resource.data,
	(data) => {
		if (data && user.data && !data.membership) {
			call('lms.lms.api.auto_enroll_resource', {
				resource_name: props.resourceName,
			}).then(() => {
				resource.reload()
			})
		}

		// Render EditorJS content for single-lesson resources
		if (data?.is_single_lesson && data?.single_lesson?.content) {
			nextTick(() => {
				renderEditor(data.single_lesson.content)
			})
		}
	}
)

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

const breadcrumbs = computed(() => [
	{
		label: __('Resources'),
		route: { name: 'Resources' },
	},
	{
		label: resource.data?.title || '',
		route: { name: 'ResourceDetail', params: { resourceName: props.resourceName } },
	},
])

usePageMeta(() => {
	return {
		title: resource.data?.title || __('Resource'),
		icon: brand.favicon,
	}
})
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
