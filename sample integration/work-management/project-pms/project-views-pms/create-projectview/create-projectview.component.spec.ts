import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CreateProjectviewComponent } from './create-projectview.component';

describe('CreateProjectviewComponent', () => {
  let component: CreateProjectviewComponent;
  let fixture: ComponentFixture<CreateProjectviewComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ CreateProjectviewComponent ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(CreateProjectviewComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
