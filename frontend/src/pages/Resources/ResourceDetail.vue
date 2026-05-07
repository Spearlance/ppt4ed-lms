<template>
	<div v-if="resource.data">
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs class="h-7" :items="breadcrumbs" />
			<div class="flex items-center space-x-2">
				<a
					v-if="user.data && resource.data.published && publicUrl"
					:href="publicUrl"
					target="_blank"
					rel="noopener"
					class="hidden sm:inline-flex items-center gap-1.5 text-xs font-medium text-ink-gray-7 hover:text-ink-gray-9 border border-outline-gray-2 hover:border-outline-gray-3 rounded-md px-2 py-1 max-w-xs truncate"
					:title="publicUrl"
					@click.prevent="copyPublicUrl"
				>
					<Link2 class="w-3.5 h-3.5 stroke-1.5 shrink-0" />
					<span class="truncate">{{ publicUrlShort }}</span>
				</a>
				<div v-if="isAdmin && tabIndex === 1" class="flex items-center space-x-2">
					<Badge v-if="childRef?.isDirty" theme="orange">
						{{ __('Not Saved') }}
					</Badge>
					<Button @click="childRef?.trashCourse()">
						<template #icon>
							<Trash2 class="w-4 h-4 stroke-1.5" />
						</template>
					</Button>
					<Button variant="solid" @click="childRef?.submitCourse()">
						{{ __('Save') }}
					</Button>
				</div>
			</div>
		</header>

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

		<!-- Admin: tabbed Overview + Content editor -->
		<div v-else-if="isAdmin">
			<Tabs :tabs="tabs" v-model="tabIndex">
				<template #tab-panel="{ tab }">
					<component
						:is="tab.component"
						:resource="resource"
						:course="resource"
						:resourceName="resourceName"
						ref="childRef"
					/>
				</template>
			</Tabs>
		</div>

		<!-- Non-admin logged-in: overview only -->
		<ResourceOverview
			v-else
			:resource="resource"
			:resourceName="resourceName"
		/>
	</div>
</template>
<script setup>
import {
	Badge,
	Breadcrumbs,
	Button,
	call,
	createResource,
	ErrorMessage,
	FormControl,
	Tabs,
	toast,
	usePageMeta,
} from 'frappe-ui'
import { computed, inject, markRaw, ref, watch } from 'vue'
import { Link2, List, Settings2, Trash2 } from 'lucide-vue-next'
import { sessionStore } from '@/stores/session'
import ResourceOverview from '@/pages/Resources/ResourceOverview.vue'
import CourseForm from '@/pages/Courses/CourseForm.vue'

const user = inject('$user')
const { brand } = sessionStore()
const email = ref('')
const emailSent = ref(false)
const tabIndex = ref(0)
const childRef = ref(null)

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

const publicUrl = computed(() => {
	const r = resource.data?.route
	return r ? `${window.location.origin}/${r}` : null
})

const publicUrlShort = computed(() => {
	const r = resource.data?.route
	return r ? `/${r}` : ''
})

async function copyPublicUrl() {
	if (!publicUrl.value) return
	try {
		await navigator.clipboard.writeText(publicUrl.value)
		toast.success(__('Public link copied'))
	} catch (e) {
		window.open(publicUrl.value, '_blank', 'noopener')
	}
}

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

const isInstructor = () => {
	if (!resource.data?.instructors) return false
	return resource.data.instructors.some((i) => i.name === user.data?.name)
}

const isAdmin = computed(() => {
	return user.data?.is_moderator || isInstructor()
})

const tabs = ref([
	{
		label: __('Overview'),
		component: markRaw(ResourceOverview),
		icon: List,
	},
	{
		label: __('Content'),
		component: markRaw(CourseForm),
		icon: Settings2,
	},
])

// Auto-enroll logged-in non-admin users so they can access the content.
watch(
	() => resource.data,
	(data) => {
		if (data && user.data && !data.membership && !isAdmin.value) {
			call('lms.lms.api.auto_enroll_resource', {
				resource_name: props.resourceName,
			}).then(() => {
				resource.reload()
			})
		}
	}
)

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
