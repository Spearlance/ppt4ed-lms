<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Edit Resource'),
			size: '3xl',
		}"
	>
		<template #body-content>
			<div class="text-base">
				<div class="grid grid-cols-2 gap-5 border-b mb-5">
					<FormControl
						v-model="form.title"
						:label="__('Title')"
						:required="true"
						autocomplete="off"
					/>
					<FormControl
						v-model="form.resource_type"
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
					<Link
						v-model="form.category"
						doctype="LMS Category"
						:label="__('Category')"
						:inlineCreate="true"
						:onCreate="createCategory"
					/>
					<MultiSelect
						v-model="form.instructors"
						doctype="User"
						:label="__('Instructors')"
						url="lms.lms.api.search_users_by_role"
						:searchParams="{
							roles: JSON.stringify(['Moderator', 'LMS Student']),
						}"
					/>
					<Uploader
						v-model="form.image"
						:label="__('Image')"
						:required="false"
					/>
				</div>
				<div class="space-y-4">
					<FormControl
						v-model="form.short_introduction"
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
							:content="form.description"
							@change="(val) => (form.description = val)"
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
				<Button variant="solid" :loading="saving" @click="saveResource(close)">
					{{ __('Save') }}
				</Button>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import { Button, call, Dialog, FormControl, TextEditor, toast } from 'frappe-ui'
import { ref, watch } from 'vue'
import Link from '@/components/Controls/Link.vue'
import { cleanError, sanitizeHTML, createLMSCategory } from '@/utils'
import MultiSelect from '@/components/Controls/MultiSelect.vue'
import Uploader from '@/components/Controls/Uploader.vue'

const show = defineModel({ required: true, default: false })
const saving = ref(false)

const props = defineProps({
	resourceDoc: {
		type: Object,
		required: true,
	},
})

const emit = defineEmits(['updated'])

const form = ref({
	title: '',
	short_introduction: '',
	description: '',
	resource_type: 'Download',
	instructors: [],
	category: null,
	image: null,
})

watch(
	() => show.value,
	(visible) => {
		if (visible && props.resourceDoc) {
			form.value = {
				title: props.resourceDoc.title || '',
				short_introduction: props.resourceDoc.short_introduction || '',
				description: props.resourceDoc.description || '',
				resource_type: props.resourceDoc.resource_type || 'Download',
				instructors: (props.resourceDoc.instructors || []).map(
					(i) => i.instructor || i.name || i
				),
				category: props.resourceDoc.category || null,
				image: props.resourceDoc.image || null,
			}
		}
	},
	{ immediate: true }
)

const createCategory = (name, done) => {
	createLMSCategory(name).then((categoryName) => {
		if (!categoryName) return
		form.value.category = categoryName
		done()
	})
}

const saveResource = async (close = () => {}) => {
	Object.keys(form.value).forEach((key) => {
		if (typeof form.value[key] === 'string') {
			form.value[key] = sanitizeHTML(form.value[key])
		}
	})

	saving.value = true
	try {
		await call('frappe.client.set_value', {
			doctype: 'LMS Course',
			name: props.resourceDoc.name,
			fieldname: {
				title: form.value.title,
				short_introduction: form.value.short_introduction,
				description: form.value.description,
				resource_type: form.value.resource_type,
				category: form.value.category,
				image: form.value.image,
				instructors: form.value.instructors.map((instructor) => ({
					instructor: instructor,
				})),
			},
		})

		toast.success(__('Resource updated successfully'))
		close()
		emit('updated')
	} catch (err) {
		toast.error(cleanError(err.messages?.[0] || err.message))
		console.error(err)
	} finally {
		saving.value = false
	}
}
</script>
