<template>
	<div v-if="resource.data">
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs class="h-7 min-w-0 flex-1 mr-2" :items="breadcrumbs" />
			<div class="flex items-center space-x-2 shrink-0">
				<a
					v-if="user.data && resource.data.published && publicUrl"
					:href="publicUrl"
					target="_blank"
					rel="noopener"
					class="hidden sm:inline-flex items-center gap-1.5 text-xs font-medium text-ink-gray-7 hover:text-ink-gray-8 border border-outline-gray-2 hover:border-outline-gray-3 rounded-md px-2 py-1 max-w-xs truncate"
					:title="publicUrl"
					@click.prevent="copyPublicUrl"
				>
					<Link2 class="w-3.5 h-3.5 stroke-1.5 shrink-0" />
					<span class="truncate">{{ publicUrlShort }}</span>
				</a>
				<div
					v-if="isAdmin && tabIndex === 1"
					class="flex items-center space-x-2"
				>
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

		<ResourceOverview v-if="!isAdmin" :resource="resource" />
		<div v-else>
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
	</div>
</template>
<script setup>
import {
	Badge,
	Button,
	createResource,
	Tabs,
	toast,
	usePageMeta,
} from 'frappe-ui'
import Breadcrumbs from '@/components/PageBreadcrumbs.vue'
import { computed, inject, markRaw, ref } from 'vue'
import { Link2, List, Settings2, Trash2 } from 'lucide-vue-next'
import { sessionStore } from '@/stores/session'
import ResourceOverview from '@/pages/Resources/ResourceOverview.vue'
import CourseForm from '@/pages/Courses/CourseForm.vue'

const user = inject('$user')
const { brand } = sessionStore()
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

const breadcrumbs = computed(() => [
	{
		label: __('Resources'),
		route: { name: 'Resources' },
	},
	{
		label: resource.data?.title || '',
		route: {
			name: 'ResourceDetail',
			params: { resourceName: props.resourceName },
		},
	},
])

usePageMeta(() => {
	return {
		title: resource.data?.title || __('Resource'),
		icon: brand.favicon,
	}
})
</script>
