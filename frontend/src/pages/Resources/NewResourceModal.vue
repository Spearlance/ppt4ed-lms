<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('New Resource'),
			size: '3xl',
		}"
	>
		<template #body-content>
			<div class="text-base">
				<div class="grid grid-cols-2 gap-5 border-b mb-5">
					<FormControl
						v-model="resource.title"
						:label="__('Title')"
						:required="true"
						autocomplete="off"
					/>
					<FormControl
						v-model="resource.resource_type"
						:label="__('Resource Type')"
						type="select"
						:options="[
							{ label: __('Video'), value: 'Video' },
							{ label: __('Download'), value: 'Download' },
							{ label: __('Article'), value: 'Article' },
							{ label: __('Mini-Course'), value: 'Mini-Course' },
							{ label: __('Template'), value: 'Template' },
						]"
						:required="true"
					/>
					<CategoryMultiPicker
						v-model="resource.categories"
						:label="__('Categories')"
						:allowCreate="true"
						:hint="__('Pick one or more categories. Manage the folder structure at /lms/admin-categories')"
					/>
					<MultiSelect
						v-model="resource.instructors"
						doctype="User"
						:label="__('Instructors')"
						url="lms.lms.api.search_users_by_role"
						:searchParams="{
							roles: JSON.stringify(['Moderator', 'LMS Student']),
						}"
					/>
					<Uploader
						v-model="resource.image"
						:label="__('Image')"
						:required="false"
					/>
				</div>
				<div class="space-y-4">
					<FormControl
						v-model="resource.short_introduction"
						:label="__('Short Introduction')"
						type="textarea"
						:required="true"
						:rows="4"
					/>
					<div>
						<div class="mb-1.5 text-sm text-ink-gray-5">
							{{ __('Description') }}
							<span class="text-ink-red-3">*</span>
						</div>
						<TextEditor
							:content="resource.description"
							@change="(val) => (resource.description = val)"
							:editable="true"
							:fixedMenu="true"
							editorClass="prose-sm max-w-none border-b border-x border-outline-gray-modals bg-surface-gray-2 rounded-b-md py-1 px-2 min-h-[10rem] max-h-[17rem] overflow-auto"
						/>
					</div>
				</div>
			</div>
		</template>
		<template #actions="{ close }">
			<div class="text-right">
				<Button variant="solid" @click="saveResource(close)">
					{{ __('Save') }}
				</Button>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import { Button, Dialog, FormControl, TextEditor, toast } from 'frappe-ui'
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import CategoryMultiPicker from '@/components/Controls/CategoryMultiPicker.vue'
import { cleanError, sanitizeHTML } from '@/utils'
import MultiSelect from '@/components/Controls/MultiSelect.vue'
import Uploader from '@/components/Controls/Uploader.vue'

const show = defineModel({ required: true, default: false })
const router = useRouter()

const props = defineProps({
	resources: {
		type: Object,
		required: true,
	},
})

const resource = ref({
	title: '',
	short_introduction: '',
	description: '',
	resource_type: 'Download',
	instructors: [],
	categories: [],
	image: null,
})

const validateFields = () => {
	Object.keys(resource.value).forEach((key) => {
		if (typeof resource.value[key] === 'string') {
			resource.value[key] = sanitizeHTML(resource.value[key])
		}
	})
}

const saveResource = (close = () => {}) => {
	validateFields()
	props.resources.insert.submit(
		{
			...resource.value,
			course_type: 'Resource',
			paid_course: 0,
			published: 1,
			published_on: new Date().toISOString().split('T')[0],
			instructors: resource.value.instructors.map((instructor) => ({
				instructor: instructor,
			})),
			categories: (resource.value.categories || []).map((c) =>
				typeof c === 'string' ? { category: c } : c
			),
		},
		{
			onSuccess(data) {
				toast.success(__('Resource created successfully'))
				close()
				router.push({
					name: 'ResourceDetail',
					params: { resourceName: data.name },
				})
			},
			onError(err) {
				toast.error(cleanError(err.messages?.[0]))
				console.error(err)
			},
		}
	)
}
</script>
