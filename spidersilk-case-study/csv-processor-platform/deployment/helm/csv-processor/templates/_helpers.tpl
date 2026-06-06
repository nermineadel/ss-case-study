{{/* Generate a standardized chart resource name identifier */}}
{{- define "csv-processor.name" -}}
{{- default .Chart.Name .Values.nameOverride | truncate 63 | trimSuffix "-" }}
{{- end }}

{{- define "csv-processor.fullname" -}}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- printf "%s-%s" .Release.Name $name | truncate 63 | trimSuffix "-" }}
{{- end }}

{{/* Base labels required for structural definitions */}}
{{- define "csv-processor.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | truncate 63 }}
{{ include "csv-processor.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
environment: {{ .Values.global.environment }}
{{- end }}

{{- define "csv-processor.selectorLabels" -}}
app.kubernetes.io/name: {{ include "csv-processor.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
