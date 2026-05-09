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

		<!-- Admin: tabbed Overview + Content editor (admin owns its own layout) -->
		<div v-if="isAdmin">
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

		<!-- Non-admin: shared hero + (claim CTA | content) -->
		<div v-else class="max-w-4xl mx-auto p-5 pt-10">
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
			<h1 class="text-3xl font-semibold text-ink-gray-9 mb-2">
				{{ resource.data.title }}
			</h1>
			<div
				v-if="resource.data.instructors?.length"
				class="flex items-center mb-4"
			>
				<span
					class="h-6 mr-1"
					:class="{ 'avatar-group overlap': resource.data.instructors.length > 1 }"
				>
					<UserAvatar
						v-for="instructor in resource.data.instructors"
						:key="instructor.name"
						:user="instructor"
					/>
				</span>
				<CourseInstructors :instructors="resource.data.instructors" />
			</div>
			<p
				v-if="resource.data.short_introduction"
				class="text-ink-gray-7 mb-6 leading-relaxed"
			>
				{{ resource.data.short_introduction }}
			</p>

			<!-- Unclaimed: explicit Claim CTA -->
			<div v-if="!resource.data.membership" class="mb-8">
				<Button
					variant="solid"
					size="lg"
					:loading="claim.loading"
					@click="claimResource()"
				>
					{{ __('Claim this Resource') }}
				</Button>
				<ErrorMessage class="mt-2" :message="claim.error" />
			</div>

			<!-- Claimed: content -->
			<ResourceOverview
				v-else
				:resource="resource"
				:resourceName="resourceName"
			/>

			<!-- Long-form description below the content / claim CTA. Rich HTML
				 from the LMS Course `description` field. -->
			<div
				v-if="resource.data.description"
				class="ProseMirror prose prose-sm max-w-none mt-10 pt-8 border-t border-outline-gray-2"
				v-html="resource.data.description"
			></div>
		</div>
	</div>
</template>
<script setup>
import {
	Badge,
	Button,
	createResource,
	ErrorMessage,
	Tabs,
	toast,
	usePageMeta,
} from 'frappe-ui'
import Breadcrumbs from '@/components/PageBreadcrumbs.vue'
import { computed, inject, markRaw, ref } from 'vue'
import { Link2, List, Settings2, Trash2 } from 'lucide-vue-next'
import { sessionStore } from '@/stores/session'
import UserAvatar from '@/components/UserAvatar.vue'
import CourseInstructors from '@/components/CourseInstructors.vue'
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

const claim = createResource({
	url: 'lms.lms.api.claim_resource',
	makeParams() {
		return { resource_name: props.resourceName }
	},
	onSuccess() {
		resource.reload()
	},
})

const claimResource = () => {
	claim.submit()
}

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
