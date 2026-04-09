<template>
    <Dialog
        v-model="show"
        :options="{
            title: __('Add New Company'),
            size: 'lg',
            actions: [
                {
                    label: __('Create Company'),
                    variant: 'solid',
                    loading: submitting,
                    onClick: ({ close }) => createCompany(close),
                },
            ],
        }"
    >
        <template #body-content>
            <div class="space-y-4">
                <FormControl
                    v-model="form.company_name"
                    :label="__('Company Name')"
                    placeholder="Acme Corp"
                    type="text"
                    :required="true"
                />
                <FormControl
                    v-model="form.admin_email"
                    :label="__('Admin Email')"
                    placeholder="admin@acme.com"
                    type="email"
                    :required="true"
                />
                <FormControl
                    v-model="form.max_seats"
                    :label="__('Max Seats')"
                    type="number"
                    :description="__('0 = unlimited')"
                />
            </div>
        </template>
    </Dialog>
</template>

<script setup lang="ts">
import { call, Dialog, FormControl, toast } from 'frappe-ui'
import { reactive, ref, watch } from 'vue'
import { cleanError } from '@/utils'

const show = defineModel<boolean>({ default: false })
const submitting = ref(false)

const emit = defineEmits<{
    created: [company: any]
}>()

const form = reactive({
    company_name: '',
    admin_email: '',
    max_seats: 0,
})

const resetForm = () => {
    form.company_name = ''
    form.admin_email = ''
    form.max_seats = 0
}

watch(show, (isOpen) => {
    if (isOpen) resetForm()
})

const createCompany = async (close?: () => void) => {
    if (!form.company_name?.trim()) {
        toast.error(__('Company name is required'))
        return
    }
    if (!form.admin_email?.trim()) {
        toast.error(__('Admin email is required'))
        return
    }

    submitting.value = true
    try {
        const result = await call('lms.lms.api.create_company_account', {
            company_name: form.company_name.trim(),
            admin_email: form.admin_email.trim(),
            max_seats: form.max_seats || 0,
        })

        toast.success(__('Company created and invite sent'))
        emit('created', result)
        resetForm()
        close?.()
    } catch (err: any) {
        toast.error(cleanError(err.messages?.[0]) || __('Unable to create company'))
    } finally {
        submitting.value = false
    }
}
</script>
