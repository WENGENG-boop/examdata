<!-- generated_by: integration-staging/tools/a14_build_artifacts.py -->

# v2 API reference (staged proposal)

Generated from the OpenAPI document of the isolated Phase A application factory
(`examdata_integration.api.app.create_app`) over private synthetic fixtures. This is
**not** a deployed endpoint list: the v2 routes are registered in the shared
application only in Phase B (B04), and the production dataset replaces the fixtures.

- prefix: `/api/v2`
- envelope schema: `examdata.v2/1`
- routes in this document: **39**
- app title: ExamData staged v2 API (Phase A)

| method | path | operationId | tags | summary |
| --- | --- | --- | --- | --- |
| GET | `/api/v2/assets/{id}` | `asset_detail_api_v2_assets__id__get` |  | Asset Detail |
| GET | `/api/v2/assets/{id}/content` | `asset_content_api_v2_assets__id__content_get` |  | Asset Content |
| HEAD | `/api/v2/assets/{id}/content` | `asset_content_api_v2_assets__id__content_head` |  | Asset Content |
| GET | `/api/v2/containers` | `containers_api_v2_containers_get` |  | Containers |
| GET | `/api/v2/containers/{id}` | `container_detail_api_v2_containers__id__get` |  | Container Detail |
| GET | `/api/v2/containers/{id}/questions` | `container_questions_api_v2_containers__id__questions_get` |  | Container Questions |
| GET | `/api/v2/containers/{id}/resources` | `container_resources_api_v2_containers__id__resources_get` |  | Container Resources |
| GET | `/api/v2/courses` | `courses_api_v2_courses_get` |  | Courses |
| GET | `/api/v2/courses/{id}` | `course_detail_api_v2_courses__id__get` |  | Course Detail |
| GET | `/api/v2/coverage` | `coverage_api_v2_coverage_get` |  | Coverage |
| GET | `/api/v2/exam-systems` | `exam_systems_api_v2_exam_systems_get` |  | Exam Systems |
| GET | `/api/v2/gaps` | `gaps_api_v2_gaps_get` |  | Gaps |
| GET | `/api/v2/info` | `info_api_v2_info_get` |  | Info |
| GET | `/api/v2/jobs/{id}` | `job_detail_api_v2_jobs__id__get` |  | Job Detail |
| GET | `/api/v2/materials` | `materials_api_v2_materials_get` |  | Materials |
| GET | `/api/v2/materials/{id}` | `material_detail_api_v2_materials__id__get` |  | Material Detail |
| GET | `/api/v2/materials/{id}/content` | `material_content_api_v2_materials__id__content_get` |  | Material Content |
| HEAD | `/api/v2/materials/{id}/content` | `material_content_api_v2_materials__id__content_head` |  | Material Content |
| GET | `/api/v2/providers` | `provider_list_api_v2_providers_get` |  | Provider List |
| GET | `/api/v2/questions` | `questions_api_v2_questions_get` |  | Questions |
| GET | `/api/v2/questions/{id}` | `question_detail_api_v2_questions__id__get` |  | Question Detail |
| GET | `/api/v2/questions/{id}/answers` | `question_answers_api_v2_questions__id__answers_get` |  | Question Answers |
| GET | `/api/v2/questions/{id}/audio` | `question_audio_api_v2_questions__id__audio_get` |  | Question Audio |
| GET | `/api/v2/questions/{id}/crop` | `question_crop_api_v2_questions__id__crop_get` |  | Question Crop |
| HEAD | `/api/v2/questions/{id}/crop` | `question_crop_api_v2_questions__id__crop_head` |  | Question Crop |
| GET | `/api/v2/questions/{id}/regions` | `question_regions_api_v2_questions__id__regions_get` |  | Question Regions |
| GET | `/api/v2/resources` | `resources_api_v2_resources_get` |  | Resources |
| GET | `/api/v2/resources/{id}` | `resource_detail_api_v2_resources__id__get` |  | Resource Detail |
| GET | `/api/v2/resources/{id}/content` | `resource_content_api_v2_resources__id__content_get` |  | Resource Content |
| HEAD | `/api/v2/resources/{id}/content` | `resource_content_api_v2_resources__id__content_head` |  | Resource Content |
| GET | `/api/v2/syllabuses` | `syllabuses_api_v2_syllabuses_get` |  | Syllabuses |
| GET | `/api/v2/syllabuses/{id}` | `syllabus_detail_api_v2_syllabuses__id__get` |  | Syllabus Detail |
| GET | `/api/v2/syllabuses/{id}/content` | `syllabus_content_api_v2_syllabuses__id__content_get` |  | Syllabus Content |
| HEAD | `/api/v2/syllabuses/{id}/content` | `syllabus_content_api_v2_syllabuses__id__content_head` |  | Syllabus Content |
| GET | `/api/v2/tags` | `tags_api_v2_tags_get` |  | Tags |
| GET | `/api/v2/tags/{id}/questions` | `tag_questions_api_v2_tags__id__questions_get` |  | Tag Questions |
| GET | `/api/v2/timetables` | `timetables_api_v2_timetables_get` |  | Timetables |
| GET | `/api/v2/timetables/events` | `timetable_events_api_v2_timetables_events_get` |  | Timetable Events |
| GET | `/api/v2/timetables/windows` | `timetable_windows_api_v2_timetables_windows_get` |  | Timetable Windows |

Every JSON response is the `examdata.v2/1` envelope; binary content and crop routes
stream fixture samples with the same error envelope for 404/413/416. The error map,
pagination and completeness semantics are defined by the staged contracts
(`examdata_integration/contracts`, `api/envelope.py`, `api/pagination.py`).
