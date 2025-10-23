import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CreateWorkitemComponent } from './create-workitem.component';

describe('CreateWorkitemComponent', () => {
  let component: CreateWorkitemComponent;
  let fixture: ComponentFixture<CreateWorkitemComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ CreateWorkitemComponent ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(CreateWorkitemComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
