"""List account-visible generation models without sending images."""
from config import Config
from classifier import Classifier

def main():
    classifier = Classifier(Config())
    try:
        for model in classifier.client.models.list():
            if 'generateContent' in (model.supported_actions or []):
                print(model.name.removeprefix('models/'))
    finally:
        classifier.close()

if __name__ == '__main__':
    main()
