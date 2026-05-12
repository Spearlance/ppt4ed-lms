<template>
	<div class="border-2 rounded-md min-w-80 max-w-sm">
		<img
			v-if="resource.data.image"
			:src="resource.data.image"
			:alt="resource.data.title"
			class="rounded-t-md w-full max-h-56 object-cover"
		/>
		<div class="p-5">
			<div class="text-2xl font-semibold mb-3 text-emerald-700">
				{{ __('Free') }}
			</div>

			<div v-if="!readOnlyMode && !isAdmin">
				<div v-if="resource.data.membership" class="space-y-2 mb-8">
					<div
						class="flex items-center text-emerald-700 text-sm font-medium"
					>
						<CheckCircle2 class="size-4 stroke-1.5" />
						<span class="ml-1.5">{{ __('You have access') }}</span>
					</div>
					<router-link
						v-if="!resource.data.is_single_lesson"
						:to="{
							name: 'Lesson',
							params: {
								courseName: resource.data.name,
								chapterNumber: currentLessonParts.chapter,
								lessonNumber: currentLessonParts.lesson,
							},
						}"
					>
						<Button variant="solid" size="md" class="w-full">
							<template #prefix>
								<BookText class="size-4 stroke-1.5" />
							</template>
							<span>
								{{
									resource.data.membership.progress > 0
										? __('Continue Learning')
										: __('Start Learning')
								}}
							</span>
						</Button>
					</router-link>
				</div>
				<div v-else class="mb-8">
					<Button
						variant="solid"
						size="md"
						class="w-full"
						:loading="claim.loading"
						@click="handleClaim"
					>
						<template #prefix>
							<Download class="size-4 stroke-1.5" />
						</template>
						<span>{{ __('Claim this Resource') }}</span>
					</Button>
					<ErrorMessage class="mt-2" :message="claim.error" />
				</div>
			</div>

			<div class="space-y-3">
				<div class="font-medium text-ink-gray-9">
					{{ __('This resource includes:') }}
				</div>
				<div
					v-if="resource.data.resource_type"
					class="flex items-center text-ink-gray-9"
				>
					<component :is="typeIcon" class="h-4 w-4 stroke-1.5" />
					<span class="ml-2">{{ resource.data.resource_type }}</span>
				</div>
				<div
					v-if="!resource.data.is_single_lesson && resource.data.lessons"
					class="flex items-center text-ink-gray-9"
				>
					<BookOpen class="h-4 w-4 stroke-1.5" />
					<span class="ml-2">
						{{ resource.data.lessons }}
						{{
							resource.data.lessons > 1
								? __('lessons')
								: __('lesson')
						}}
					</span>
				</div>
				<div class="flex items-center text-ink-gray-9 font-semibold">
					<Sparkles class="h-4 w-4 stroke-2" />
					<span class="ml-2">{{ __('Free access — no credit card') }}</span>
				</div>
			</div>
		</div>
	</div>

	<RegisterModal
		v-model:open="showRegister"
		target-type="resource"
		:target-slug="resource.data.name"
		intent="free"
		:context-label="resource.data.title"
		:redirect-url="`/lms/resources/${resource.data.name}`"
	/>
</template>
<script setup>
import {
	BookOpen,
	BookText,
	CheckCircle2,
	Download,
	FileText,
	GraduationCap,
	Sparkles,
	Video,
} from 'lucide-vue-next'
import { computed, inject, ref } from 'vue'
import { Button, createResource, ErrorMessage, toast } from 'frappe-ui'
import { useTelemetry } from 'frappe-ui/frappe'
import RegisterModal from '@/components/Modals/RegisterModal.vue'

const user = inject('$user')
const readOnlyMode = window.read_only_mode
const { capture } = useTelemetry()

const props = defineProps({
	resource: {
		type: Object,
		required: true,
	},
})

const showRegister = ref(false)

const claim = createResource({
	url: 'lms.lms.api.claim_resource',
	makeParams() {
		return { resource_name: props.resource.data.name }
	},
	onSuccess() {
		capture('claimed_resource', { resource: props.resource.data.name })
		toast.success(__('Resource claimed'))
		props.resource.reload()
	},
})

function handleClaim() {
	if (!user.data) {
		showRegister.value = true
		return
	}
	claim.submit()
}

const isInstructor = computed(() => {
	if (!props.resource.data?.instructors) return false
	return props.resource.data.instructors.some(
		(i) => i.name === user.data?.name
	)
})

const isAdmin = computed(() => {
	return isInstructor.value
})

const currentLessonParts = computed(() => {
	const cl = props.resource.data?.current_lesson
	if (!cl) return { chapter: 1, lesson: 1 }
	const parts = cl.split('-')
	return { chapter: parts[0] || 1, lesson: parts[1] || 1 }
})

const typeIcon = computed(() => {
	switch (props.resource.data?.resource_type) {
		case 'Video':
			return Video
		case 'Download':
			return Download
		case 'Article':
			return FileText
		case 'Mini-Course':
			return GraduationCap
		case 'Template':
			return FileText
		default:
			return FileText
	}
})
</script>
