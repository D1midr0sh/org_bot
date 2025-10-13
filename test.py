import openai

YANDEX_CLOUD_FOLDER = "b1gi512d1m3olrb0k745"
YANDEX_CLOUD_API_KEY = "AQVN11Et5owsOOaK61Q8_rCJ-2xcsFy-jn63Uhxd"

client = openai.OpenAI(
    api_key=YANDEX_CLOUD_API_KEY,
    base_url="https://rest-assistant.api.cloud.yandex.net/v1",
    project= YANDEX_CLOUD_FOLDER
)

response = client.responses.create(
    model=f"gpt://{YANDEX_CLOUD_FOLDER}/yandexgpt/latest",
    input="Придумай 3 необычные идеи для стартапа в сфере путешествий.",
    temperature=0.8,
    max_output_tokens=1500
)

print(response.output[0].content[0].text)
